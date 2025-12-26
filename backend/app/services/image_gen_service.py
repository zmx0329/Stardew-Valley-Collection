from __future__ import annotations

import base64
from io import BytesIO
import logging
from uuid import uuid4

import httpx
from PIL import Image

from ..config import Settings
from ..models.image_gen import ImageGenRequest, ImageGenResponse
from .errors import ImageGenerationError, StorageError
from .utils import decode_base64_image


class ImageGenerationService:
  """Generates pixel-style images; uses remote model if配置，否则本地像素化兜底."""

  def __init__(self, settings: Settings):
    self.settings = settings
    self.logger = logging.getLogger(__name__)

  async def generate(self, payload: ImageGenRequest) -> ImageGenResponse:
    image_bytes = decode_base64_image(payload.image_base64)
    last_error: ImageGenerationError | None = None

    if self.settings.image_gen_endpoint and self.settings.image_gen_key:
      try:
        generated = await self._call_remote_model(image_bytes, payload)
        return ImageGenResponse(image_base64=generated, source="remote")
      except ImageGenerationError as exc:
        # fall back to local pixelation
        last_error = exc
      except Exception as exc:  # pragma: no cover - defensive
        last_error = ImageGenerationError("image_gen_error", f"生图调用失败: {exc}")

    fallback = self._pixelate_local(image_bytes, payload.block_size)
    note = last_error.message if last_error else "生图服务未配置或调用失败，已使用本地像素化"
    return ImageGenResponse(image_base64=fallback, source="fallback", note=note)

  async def _call_remote_model(self, image_bytes: bytes, payload: ImageGenRequest) -> str:
    endpoint = self.settings.image_gen_endpoint
    api_key = self.settings.image_gen_key
    model = self.settings.image_gen_model or "qwen-image-edit-plus"
    prompt = (
      payload.prompt
      or "将图片中的主要物品转换成《星露谷物语》风格的 16 位像素艺术。严格保持物体原有的轮廓和比例，不要改变其形态。 使用游戏特有的温暖、朴实调色板，块状精灵图纹理，增加复古光影，使其看起来像可以直接放入游戏中的素材。"
    )

    use_doubao = self._looks_like_doubao(endpoint, model)
    if use_doubao:
      resolved_model = self._resolve_doubao_model(model)
      return await self._call_doubao_image_generation(
        endpoint, api_key, resolved_model, image_bytes, prompt
      )

    use_qwen = "dashscope.aliyuncs.com" in (endpoint or "") or model.startswith("qwen-")
    if use_qwen:
      return await self._call_qwen_image_edit(endpoint, api_key, model, image_bytes, prompt)

    return await self._call_gemini(endpoint, api_key, model, image_bytes, prompt)

  def _looks_like_doubao(self, endpoint: str | None, model: str | None) -> bool:
    if model and model.startswith("doubao-"):
      return True
    if not endpoint:
      return False
    lowered = endpoint.lower()
    return "volces.com" in lowered or "ark.cn" in lowered or "/api/v3/images/generations" in lowered

  def _resolve_doubao_model(self, model: str | None) -> str:
    if not model or model == "qwen-image-edit-plus":
      return "doubao-seedream-4-5-251128"
    return model

  async def _call_gemini(
    self, endpoint: str, api_key: str, model: str, image_bytes: bytes, prompt: str
  ) -> str:
    headers = {"Content-Type": "application/json"}
    body = {
      "contents": [
        {
          "parts": [
            {
              "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
              }
            },
            {"text": prompt},
          ]
        }
      ],
      "model": model,
    }
    data = await self._post_json(endpoint, headers, body, params={"key": api_key})
    if "image_base64" in data and isinstance(data["image_base64"], str):
      return data["image_base64"]

    candidates = data.get("candidates") or data.get("predictions") or []
    if candidates:
      first = candidates[0]
      parts = first.get("content", {}).get("parts") if isinstance(first, dict) else None
      if isinstance(parts, list):
        for part in parts:
          inline = part.get("inline_data") if isinstance(part, dict) else None
          if inline and isinstance(inline.get("data"), str):
            return f"data:{inline.get('mime_type', 'image/png')};base64,{inline['data']}"

    raise ImageGenerationError("invalid_response", "生图响应不可用", status_code=502)

  async def _call_qwen_image_edit(
    self, endpoint: str, api_key: str, model: str, image_bytes: bytes, prompt: str
  ) -> str:
    target_endpoint = endpoint.rstrip("/")
    if "aigc/image-editing" in target_endpoint:
      target_endpoint = target_endpoint.replace("aigc/image-editing", "aigc/multimodal-generation/generate")
    elif target_endpoint.endswith("/api/v1"):
      target_endpoint = f"{target_endpoint}/services/aigc/multimodal-generation/generate"
    image_url, png_bytes = await self._upload_public_image(image_bytes)
    self.logger.info("Qwen image edit using url: %s", image_url)
    await self._assert_public_url(image_url)
    try:
      return await self._call_qwen_image_edit_payload(
        target_endpoint, api_key, model, prompt, image_url
      )
    except ImageGenerationError as exc:
      message = (exc.message or "").lower()
      if "url error" not in message:
        raise
      data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")
      self.logger.info("Qwen image edit retry with data URL payload")
      return await self._call_qwen_image_edit_payload(
        target_endpoint, api_key, model, prompt, data_url
      )

  async def _call_qwen_image_edit_payload(
    self, endpoint: str, api_key: str, model: str, prompt: str, image_input: str
  ) -> str:
    body = {
      "model": model,
      "input": {
        "messages": [
          {
            "role": "user",
            "content": [
              {"image": image_input},
              {"text": prompt},
            ],
          }
        ]
      },
      "parameters": {
        "n": 1,
        "watermark": False,
        "negative_prompt": "低质量",
        "prompt_extend": True,
      },
    }
    headers = {
      "Authorization": f"Bearer {api_key}",
      "X-DashScope-Api-Key": api_key,
      "Content-Type": "application/json",
    }
    data = await self._post_json(endpoint, headers, body)
    return await self._extract_qwen_image(data)

  async def _call_doubao_image_generation(
    self, endpoint: str, api_key: str, model: str, image_bytes: bytes, prompt: str
  ) -> str:
    image_input = await self._prepare_doubao_image_input(image_bytes)
    body = {
      "model": model,
      "prompt": prompt,
      "image": image_input,
      "sequential_image_generation": "disabled",
      "response_format": "url",
      "size": "2K",
      "stream": False,
      "watermark": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = await self._post_json(endpoint, headers, body)
    return await self._extract_doubao_image(data)

  async def _prepare_doubao_image_input(self, image_bytes: bytes) -> str:
    try:
      image_url, _ = await self._upload_public_image(image_bytes)
      self.logger.info("Doubao image gen using url: %s", image_url)
      await self._assert_public_url(image_url)
      return image_url
    except ImageGenerationError as exc:
      if exc.code not in ("image_gen_config", "image_gen_upload"):
        raise
      png_bytes = self._encode_png(image_bytes)
      data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")
      self.logger.info("Doubao image gen fallback to data URL input (%s).", exc.code)
      return data_url

  async def _upload_public_image(self, image_bytes: bytes) -> tuple[str, bytes]:
    storage = self._build_public_storage()
    if not storage:
      raise ImageGenerationError("image_gen_config", "生图服务需要公网图片地址", status_code=500)

    key = f"image-gen/{uuid4().hex}.png"
    try:
      png_bytes = self._encode_png(image_bytes)
      url = await storage.upload_image(key, png_bytes, content_type="image/png")
      return url, png_bytes
    except StorageError as exc:
      raise ImageGenerationError("image_gen_upload", exc.message, status_code=502) from exc

  def _build_public_storage(self):
    if (
      self.settings.oss_endpoint
      and self.settings.oss_bucket
      and (self.settings.oss_access_key_id or self.settings.aliyun_access_key_id)
      and (self.settings.oss_access_key_secret or self.settings.aliyun_access_key_secret)
    ):
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
        pass

    if self.settings.supabase_url and self.settings.supabase_key:
      from ..clients.storage_client import SupabaseStorageClient

      try:
        return SupabaseStorageClient(
          self.settings.supabase_url,
          self.settings.supabase_key,
          self.settings.supabase_bucket,
          self.settings.supabase_table,
        )
      except StorageError:
        return None

    return None

  def _encode_png(self, image_bytes: bytes) -> bytes:
    try:
      with Image.open(BytesIO(image_bytes)) as image:
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
          image = image.convert("RGBA")
        else:
          image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:  # pragma: no cover - defensive
      raise ImageGenerationError("invalid_image", "无法读取图像") from exc

  async def _assert_public_url(self, url: str) -> None:
    try:
      async with httpx.AsyncClient(timeout=6.0) as client:
        response = await client.get(url)
      if response.status_code >= 400:
        raise ImageGenerationError(
          "image_gen_upload",
          f"生图图片无法访问: status={response.status_code}",
          status_code=502,
        )
    except httpx.TimeoutException as exc:
      raise ImageGenerationError("timeout", "生图图片访问超时", status_code=504) from exc
    except httpx.RequestError as exc:
      raise ImageGenerationError("image_gen_upload", "生图图片访问失败", status_code=502) from exc

  async def _extract_qwen_image(self, data: dict) -> str:
    output = data.get("output", {}) if isinstance(data.get("output"), dict) else {}
    results = output.get("results") or output.get("images") or output.get("choices") or []
    if isinstance(results, list):
      for item in results:
        if isinstance(item, str):
          return await self._resolve_image_ref(item)
        if isinstance(item, dict):
          message = item.get("message")
          if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
              for part in content:
                if isinstance(part, dict):
                  value = part.get("image") or part.get("url")
                  if isinstance(value, str):
                    return await self._resolve_image_ref(value)
          for key in ("image", "url", "b64_json", "base64"):
            value = item.get(key)
            if isinstance(value, str):
              return await self._resolve_image_ref(value)

    for key in ("image", "url", "b64_json", "base64"):
      value = output.get(key)
      if isinstance(value, str):
        return await self._resolve_image_ref(value)

    raise ImageGenerationError("invalid_response", "生图响应不可用", status_code=502)

  async def _extract_doubao_image(self, data: dict) -> str:
    if isinstance(data, dict):
      for key in ("data", "images", "results", "output"):
        items = data.get(key)
        if isinstance(items, list):
          for item in items:
            if isinstance(item, str):
              return await self._resolve_image_ref(item)
            if isinstance(item, dict):
              for field in ("url", "image", "b64_json", "base64"):
                value = item.get(field)
                if isinstance(value, str):
                  return await self._resolve_image_ref(value)
        elif isinstance(items, dict):
          for field in ("url", "image", "b64_json", "base64"):
            value = items.get(field)
            if isinstance(value, str):
              return await self._resolve_image_ref(value)

      for field in ("url", "image", "b64_json", "base64"):
        value = data.get(field)
        if isinstance(value, str):
          return await self._resolve_image_ref(value)

    raise ImageGenerationError("invalid_response", "生图响应不可用", status_code=502)

  async def _resolve_image_ref(self, ref: str) -> str:
    if ref.startswith("data:image/"):
      return ref
    if ref.startswith("http://") or ref.startswith("https://"):
      return await self._fetch_image_url(ref)
    return f"data:image/png;base64,{ref}"

  async def _fetch_image_url(self, url: str) -> str:
    try:
      async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      raise ImageGenerationError("image_gen_error", "生图图片拉取失败", status_code=status) from exc
    except httpx.TimeoutException as exc:
      raise ImageGenerationError("timeout", "生图图片拉取超时", status_code=504) from exc
    except Exception as exc:  # pragma: no cover - defensive
      raise ImageGenerationError("image_gen_error", "生图图片拉取失败") from exc

    mime = response.headers.get("content-type", "image/png").split(";")[0]
    return f"data:{mime};base64," + base64.b64encode(response.content).decode("utf-8")

  async def _post_json(self, endpoint: str, headers: dict, body: dict, params: dict | None = None) -> dict:
    try:
      async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(endpoint, headers=headers, params=params, json=body)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      if status == 401:
        raise ImageGenerationError("unauthorized", "生图服务认证失败", status_code=401) from exc
      if status == 429:
        raise ImageGenerationError("rate_limited", "生图服务繁忙，请稍后重试", status_code=429) from exc
      detail = self._extract_error_detail(exc.response)
      message = f"生图服务返回错误: {detail}" if detail else "生图服务返回错误"
      raise ImageGenerationError("image_gen_error", message, status_code=status) from exc
    except httpx.TimeoutException as exc:
      raise ImageGenerationError("timeout", "生图服务超时", status_code=504) from exc
    except Exception as exc:  # pragma: no cover - defensive
      raise ImageGenerationError("image_gen_error", "生图调用失败") from exc

    return response.json()

  def _extract_error_detail(self, response: httpx.Response) -> str | None:
    try:
      payload = response.json()
    except ValueError:
      text = response.text.strip()
      return text[:300] if text else None

    if isinstance(payload, dict):
      if isinstance(payload.get("error"), dict):
        msg = payload["error"].get("message") or payload["error"].get("code")
        if isinstance(msg, str):
          return msg
      if isinstance(payload.get("message"), str):
        return payload["message"]
      if isinstance(payload.get("code"), str):
        return payload["code"]

    return None

  def _pixelate_local(self, image_bytes: bytes, block_size: int) -> str:
    try:
      image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:  # pragma: no cover - defensive
      raise ImageGenerationError("invalid_image", "无法读取图像") from exc

    block = max(2, min(block_size, 64))
    small_w = max(1, image.width // block)
    small_h = max(1, image.height // block)
    small = image.resize((small_w, small_h), resample=Image.NEAREST)
    pixelated = small.resize((image.width, image.height), resample=Image.NEAREST)

    buffer = BytesIO()
    pixelated.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
