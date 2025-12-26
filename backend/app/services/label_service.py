from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from PIL import Image

from ..clients.label_client import LabelGenClient
from ..config import Settings
from ..models.label import LabelRequest, LabelResponse
from .errors import LabelGenerationError, StorageError
from .utils import decode_base64_image


class LabelService:
  """Generate a Chinese object name from the selected crop."""

  def __init__(self, settings: Settings):
    self.settings = settings
    self.provider = (settings.label_gen_provider or "gemini").lower()
    self.client = (
      LabelGenClient(
        settings.label_gen_endpoint,
        settings.label_gen_key,
        settings.label_gen_model,
        self.provider,
      )
      if settings.label_gen_endpoint and settings.label_gen_key
      else None
    )
    self.storage = self._build_storage()

  def _build_storage(self):
    if self.provider != "qwen":
      return None
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

  async def generate_label(self, payload: LabelRequest) -> LabelResponse:
    if not self.client:
      raise LabelGenerationError("label_config", "未配置命名模型", status_code=500)

    try:
      image_bytes = decode_base64_image(payload.image_base64)
    except Exception as exc:
      raise LabelGenerationError("invalid_image", "无法解析图像内容", status_code=400) from exc
    try:
      image = Image.open(BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - defensive
      raise LabelGenerationError("invalid_image", "无法读取图片", status_code=400) from exc

    width, height = image.size
    x0 = max(0, int(payload.bounds.x * width))
    y0 = max(0, int(payload.bounds.y * height))
    x1 = min(width, int((payload.bounds.x + payload.bounds.width) * width))
    y1 = min(height, int((payload.bounds.y + payload.bounds.height) * height))

    if x1 <= x0 or y1 <= y0:
      raise LabelGenerationError("invalid_bounds", "裁剪范围无效", status_code=400)

    cropped = image.crop((x0, y0, x1, y1))
    buffer = BytesIO()
    cropped.save(buffer, format="PNG")
    cropped_bytes = buffer.getvalue()
    if self.provider == "qwen":
      if not self.storage:
        raise LabelGenerationError("label_config", "未配置 OSS", status_code=500)
      try:
        key = f"label-temp/{uuid4().hex}.png"
        image_url = await self.storage.upload_image(key, cropped_bytes, content_type="image/png")
      except StorageError as exc:
        raise LabelGenerationError("label_upload", exc.message, status_code=502) from exc
      label = await self.client.generate_label(None, payload.hint, image_url=image_url)
    else:
      label = await self.client.generate_label(cropped_bytes, payload.hint)
    return LabelResponse(label=label)
