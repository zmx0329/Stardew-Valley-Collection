from __future__ import annotations

from io import BytesIO
import logging
from uuid import uuid4
from typing import List

from PIL import Image

from ..clients.detection_client import AliyunDetectionClient, AzureDetectionClient
from ..clients.label_client import LabelGenClient
from ..config import Settings
from ..models.common import DetectionBox, ImageSize, NormalizedBounds
from ..models.detection import DetectResponse
from .errors import DetectionError, LabelGenerationError, StorageError
from .utils import clamp


class DetectionService:
  """Handles object detection with Azure CV or deterministic fallback."""

  def __init__(self, settings: Settings):
    self.settings = settings
    self.logger = logging.getLogger(__name__)
    self.label_provider = (settings.label_gen_provider or "gemini").lower()
    self.label_client = (
      LabelGenClient(
        settings.label_gen_endpoint,
        settings.label_gen_key,
        settings.label_gen_model,
        self.label_provider,
      )
      if settings.label_gen_endpoint and settings.label_gen_key
      else None
    )

  async def detect(self, image_bytes: bytes, max_results: int) -> DetectResponse:
    try:
      image = Image.open(BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - defensive
      raise DetectionError("invalid_image", "无法读取图片", status_code=400) from exc

    width, height = image.size

    try:
      if (
        self.settings.aliyun_access_key_id
        and self.settings.aliyun_access_key_secret
        and self.settings.oss_endpoint
        and self.settings.oss_bucket
      ):
        boxes = await self._detect_with_aliyun(image_bytes, width, height, max_results)
      elif self.settings.azure_cv_endpoint and self.settings.azure_cv_key:
        client = AzureDetectionClient(self.settings.azure_cv_endpoint, self.settings.azure_cv_key)
        boxes = await client.detect(image_bytes, width, height, max_results)
        if not boxes:
          raise DetectionError("no_objects", "未识别到物体", status_code=422)
      else:
        boxes = self._fallback_boxes(width, height, max_results)
    except DetectionError as exc:
      # 如果云端检测失败，退回到兜底框，保证前端流程可走通
      self.logger.warning("Detection fallback: %s - %s", exc.code, exc.message)
      boxes = self._fallback_boxes(width, height, max_results)

    if self.label_client:
      boxes = await self._generate_chinese_labels(image, boxes)

    return DetectResponse(boxes=boxes, image_size=ImageSize(width=width, height=height))

  async def _detect_with_aliyun(self, image_bytes: bytes, width: int, height: int, max_results: int) -> list[DetectionBox]:
    from ..clients.oss_client import OssStorageClient

    try:
      access_key_id = self.settings.oss_access_key_id or self.settings.aliyun_access_key_id or ""
      access_key_secret = self.settings.oss_access_key_secret or self.settings.aliyun_access_key_secret or ""
      storage = OssStorageClient(
        endpoint=self.settings.oss_endpoint or "",
        bucket=self.settings.oss_bucket or "",
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        public_base_url=self.settings.oss_public_endpoint,
      )
      filename = f"detect-temp/{uuid4().hex}.png"
      public_url = await storage.upload_image(filename, image_bytes, content_type="image/png")
      client = AliyunDetectionClient(
        self.settings.aliyun_access_key_id or "",
        self.settings.aliyun_access_key_secret or "",
        self.settings.aliyun_region,
        self.settings.aliyun_endpoint,
      )
      return await client.detect_by_url(public_url, width, height, max_results)
    except DetectionError:
      raise
    except StorageError as exc:
      raise DetectionError("aliyun_upload", exc.message) from exc
    except Exception as exc:
      raise DetectionError("aliyun_upload", f"上传图片到存储失败: {exc}") from exc

  def _fallback_boxes(self, width: int, height: int, max_results: int) -> List[DetectionBox]:
    aspect = width / height if height else 1.0
    if aspect >= 1:
      specs = [
        {"x": 0.2, "y": 0.16, "w": 0.48, "h": 0.42, "label": "主物体", "conf": 0.9},
        {"x": 0.65, "y": 0.2, "w": 0.22, "h": 0.26, "label": "前景物体", "conf": 0.82},
        {"x": 0.28, "y": 0.58, "w": 0.26, "h": 0.28, "label": "次物体", "conf": 0.76},
      ]
    else:
      specs = [
        {"x": 0.22, "y": 0.12, "w": 0.44, "h": 0.5, "label": "主物体", "conf": 0.9},
        {"x": 0.18, "y": 0.64, "w": 0.28, "h": 0.26, "label": "左侧物体", "conf": 0.78},
        {"x": 0.58, "y": 0.64, "w": 0.24, "h": 0.26, "label": "右侧物体", "conf": 0.74},
      ]

    boxes: list[DetectionBox] = []
    for index, spec in enumerate(specs):
      if index >= max_results:
        break
      bounds = NormalizedBounds(
        x=clamp(spec["x"], 0, 1),
        y=clamp(spec["y"], 0, 1),
        width=clamp(spec["w"], 0.05, 0.95),
        height=clamp(spec["h"], 0.05, 0.95),
      )
      boxes.append(
        DetectionBox(
          id=f"box-{index + 1}",
          label=spec["label"],
          confidence=spec["conf"],
          bounds=bounds,
        )
      )

    if not boxes:  # pragma: no cover - defensive, should not happen
      boxes.append(
        DetectionBox(
          id="box-1",
          label="物体",
          confidence=0.7,
          bounds=NormalizedBounds(x=0.25, y=0.25, width=0.4, height=0.4),
        )
      )

    return boxes

  async def _generate_chinese_labels(self, image: Image.Image, boxes: list[DetectionBox]) -> list[DetectionBox]:
    if not self.label_client:
      return boxes

    updated: list[DetectionBox] = []
    width, height = image.size
    storage = None
    if self.label_provider == "qwen":
      storage = self._build_label_storage()

    for box in boxes:
      cropped = self._crop_image(image, width, height, box.bounds)
      if cropped is None:
        updated.append(box)
        continue
      try:
        image_url = None
        if storage:
          key = f"label-temp/{uuid4().hex}.png"
          image_url = await storage.upload_image(key, cropped, content_type="image/png")
        name = await self.label_client.generate_label(cropped, box.label, image_url=image_url)
      except LabelGenerationError as exc:
        self.logger.warning("Label generation failed: %s - %s", exc.code, exc.message)
        updated.append(box)
        continue
      except StorageError as exc:
        self.logger.warning("Label generation failed: %s", exc.message)
        updated.append(box)
        continue
      except Exception as exc:  # pragma: no cover - defensive
        self.logger.warning("Label generation failed: %s", exc)
        updated.append(box)
        continue

      if name:
        updated.append(box.model_copy(update={"label": name}))
      else:
        updated.append(box)

    return updated

  def _build_label_storage(self):
    if not (self.settings.oss_endpoint and self.settings.oss_bucket):
      return None
    from ..clients.oss_client import OssStorageClient

    access_key_id = self.settings.oss_access_key_id or self.settings.aliyun_access_key_id or ""
    access_key_secret = self.settings.oss_access_key_secret or self.settings.aliyun_access_key_secret or ""
    try:
      return OssStorageClient(
        endpoint=self.settings.oss_endpoint or "",
        bucket=self.settings.oss_bucket or "",
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        public_base_url=self.settings.oss_public_endpoint,
      )
    except StorageError:
      return None

  def _crop_image(self, image: Image.Image, width: int, height: int, bounds: NormalizedBounds) -> bytes | None:
    x0 = max(0, int(bounds.x * width))
    y0 = max(0, int(bounds.y * height))
    x1 = min(width, int((bounds.x + bounds.width) * width))
    y1 = min(height, int((bounds.y + bounds.height) * height))

    if x1 <= x0 or y1 <= y0:
      return None

    try:
      cropped = image.crop((x0, y0, x1, y1))
      buffer = BytesIO()
      cropped.save(buffer, format="PNG")
      return buffer.getvalue()
    except Exception:
      return None
