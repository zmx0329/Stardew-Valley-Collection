from __future__ import annotations

import base64
import httpx
import anyio
from typing import Any

from ..models.common import DetectionBox, NormalizedBounds
from ..services.errors import DetectionError
from ..services.utils import clamp


class AzureDetectionClient:
  """Thin wrapper over Azure Computer Vision object detection."""

  def __init__(self, endpoint: str, api_key: str) -> None:
    self.endpoint = endpoint.rstrip("/")
    self.api_key = api_key

  async def detect(self, image_bytes: bytes, image_width: int, image_height: int, max_results: int) -> list[DetectionBox]:
    if not self.endpoint or not self.api_key:
      raise DetectionError("azure_config", "未配置 Azure CV", status_code=500)

    url = f"{self.endpoint}/vision/v3.2/detect"
    headers = {"Ocp-Apim-Subscription-Key": self.api_key, "Content-Type": "application/octet-stream"}

    async with httpx.AsyncClient(timeout=10.0) as client:
      response = await client.post(url, headers=headers, content=image_bytes)

    try:
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      if status == 401:
        raise DetectionError("unauthorized", "Azure CV 密钥无效", status_code=401) from exc
      if status == 429:
        raise DetectionError("rate_limited", "Azure CV 限流，请稍后重试", status_code=429) from exc
      if status == 408:
        raise DetectionError("timeout", "Azure CV 超时", status_code=408) from exc
      raise DetectionError("azure_error", "Azure CV 调用失败", status_code=status) from exc

    data = response.json()
    objects = data.get("objects") or []
    return self._parse_objects(objects, image_width, image_height, max_results)

  def _parse_objects(
    self, objects: list[dict], image_width: int, image_height: int, max_results: int
  ) -> list[DetectionBox]:
    boxes: list[DetectionBox] = []

    for index, obj in enumerate(objects):
      if index >= max_results:
        break
      rectangle = obj.get("rectangle") or obj.get("boundingBox") or {}
      width = rectangle.get("w") or rectangle.get("width")
      height = rectangle.get("h") or rectangle.get("height")
      x = rectangle.get("x") or rectangle.get("left")
      y = rectangle.get("y") or rectangle.get("top")

      if width is None or height is None or x is None or y is None:
        continue

      normalized = NormalizedBounds(
        x=clamp(x / image_width, 0, 1),
        y=clamp(y / image_height, 0, 1),
        width=clamp(width / image_width, 0, 1),
        height=clamp(height / image_height, 0, 1),
      )
      boxes.append(
        DetectionBox(
          id=str(obj.get("object", f"box-{index + 1}")),
          label=obj.get("object"),
          confidence=obj.get("confidence"),
          bounds=normalized,
        )
      )

    return boxes


class AliyunDetectionClient:
  """Alibaba Cloud ObjectDet wrapper."""

  def __init__(self, access_key: str, access_secret: str, region: str, endpoint: str):
    try:
      from alibabacloud_objectdet20191230.client import Client as ObjectdetClient  # type: ignore
      from alibabacloud_objectdet20191230 import models as objectdet_models  # type: ignore
      from alibabacloud_tea_openapi import models as open_api_models  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard for optional dep
      raise DetectionError("aliyun_dependency", "缺少阿里云检测依赖，请安装 requirements") from exc

    config = open_api_models.Config(
      access_key_id=access_key,
      access_key_secret=access_secret,
      region_id=region,
      endpoint=endpoint,
    )
    self.client = ObjectdetClient(config)

  async def detect_by_url(
    self, image_url: str, image_width: int, image_height: int, max_results: int
  ) -> list[DetectionBox]:
    # objectdet_models is imported lazily above
    from alibabacloud_objectdet20191230 import models as objectdet_models  # type: ignore

    try:
      request = objectdet_models.DetectObjectRequest(image_url=image_url)
      # SDK is sync; run in thread to avoid blocking event loop
      response = await anyio.to_thread.run_sync(self.client.detect_object, request)
    except Exception as exc:
      detail = getattr(exc, "message", None) or str(exc)
      code = getattr(exc, "code", None)
      if code:
        detail = f"{detail} (code={code})"
      raise DetectionError("aliyun_error", f"阿里云检测失败: {detail}", status_code=502) from exc

    elements = (response.body.data.elements or [])[:max_results]
    boxes: list[DetectionBox] = []
    for index, element in enumerate(elements):
      coords = getattr(element, "boxes", None)
      if not coords and hasattr(element, "to_map"):
        coords = element.to_map().get("Boxes")
      if not coords or len(coords) < 4:
        continue
      x, y, w, h = coords[:4]

      bounds = NormalizedBounds(
        x=clamp(x / image_width, 0, 1),
        y=clamp(y / image_height, 0, 1),
        width=clamp(w / image_width, 0, 1),
        height=clamp(h / image_height, 0, 1),
      )
      boxes.append(
        DetectionBox(
          id=element.type or f"box-{index + 1}",
          label=element.type,
          confidence=element.score,
          bounds=bounds,
        )
      )

    if not boxes:
      raise DetectionError("no_objects", "未识别到物体", status_code=422)
    return boxes
