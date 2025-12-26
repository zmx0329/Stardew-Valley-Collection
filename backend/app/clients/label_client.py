from __future__ import annotations

import base64

import httpx

from ..services.errors import LabelGenerationError


class LabelGenClient:
  """Multi-modal label generator for object names."""

  def __init__(self, endpoint: str, api_key: str, model: str | None, provider: str = "gemini") -> None:
    self.endpoint = endpoint
    self.api_key = api_key
    self.model = model or "gemini-1.5-pro"
    self.provider = (provider or "gemini").lower()

  async def generate_label(
    self,
    image_bytes: bytes | None,
    hint: str | None = None,
    image_url: str | None = None,
  ) -> str:
    if not self.endpoint or not self.api_key:
      raise LabelGenerationError("label_config", "未配置命名模型", status_code=500)

    prompt = (
      "请根据图片识别主要物体，给出一个星露谷风格的中文物品名（2-6个字）。"
      "不要解释，不要加标点，只输出名称。"
    )
    if hint:
      prompt = f"{prompt} 如需参考，英文标签是：{hint}"

    if self.provider == "qwen":
      return await self._call_qwen(image_bytes, image_url, prompt)
    return await self._call_gemini(image_bytes, prompt)

  async def _call_gemini(self, image_bytes: bytes | None, prompt: str) -> str:
    if not image_bytes:
      raise LabelGenerationError("invalid_image", "命名服务缺少图像内容", status_code=400)
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
    }

    headers = {"Content-Type": "application/json"}
    params = {"key": self.api_key}

    try:
      async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(self.endpoint, headers=headers, params=params, json=body)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      detail = ""
      try:
        detail = exc.response.text
      except Exception:
        detail = ""
      if status == 401:
        raise LabelGenerationError("unauthorized", f"命名服务认证失败: {detail}", status_code=401) from exc
      if status == 429:
        raise LabelGenerationError("rate_limited", f"命名服务繁忙，请稍后再试: {detail}", status_code=429) from exc
      raise LabelGenerationError("label_error", f"命名服务返回错误: {detail}", status_code=status) from exc
    except httpx.TimeoutException as exc:
      raise LabelGenerationError("timeout", "命名服务超时", status_code=504) from exc
    except Exception as exc:  # pragma: no cover - defensive
      raise LabelGenerationError("label_error", "命名服务调用失败") from exc

    data = response.json()
    text = self._extract_text(data)
    cleaned = self._clean_label(text)
    if not cleaned:
      raise LabelGenerationError("invalid_response", "命名响应不可用", status_code=502)
    return cleaned

  async def _call_qwen(self, image_bytes: bytes | None, image_url: str | None, prompt: str) -> str:
    if not image_url:
      raise LabelGenerationError("invalid_image", "命名服务需要公网图片地址", status_code=400)
    if "compatible-mode" in self.endpoint:
      return await self._call_qwen_compatible(image_url, prompt)

    body = {
      "model": self.model or "qwen2-vl-plus",
      "input": {
        "messages": [
          {
            "role": "user",
            "content": [
              {"image": {"image_url": image_url}},
              {"text": prompt},
            ],
          },
        ]
      },
    }
    headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {self.api_key}",
      "X-DashScope-Api-Key": self.api_key,
    }

    try:
      async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(self.endpoint, headers=headers, json=body)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      detail = ""
      try:
        detail = exc.response.text
      except Exception:
        detail = ""
      if status == 401:
        raise LabelGenerationError("unauthorized", f"命名服务认证失败: {detail}", status_code=401) from exc
      if status == 429:
        raise LabelGenerationError("rate_limited", f"命名服务繁忙，请稍后再试: {detail}", status_code=429) from exc
      raise LabelGenerationError("label_error", f"命名服务返回错误: {detail}", status_code=status) from exc
    except httpx.TimeoutException as exc:
      raise LabelGenerationError("timeout", "命名服务超时", status_code=504) from exc
    except Exception as exc:  # pragma: no cover - defensive
      raise LabelGenerationError("label_error", "命名服务调用失败") from exc

    data = response.json()
    text = self._extract_qwen_text(data)
    cleaned = self._clean_label(text)
    if not cleaned:
      raise LabelGenerationError("invalid_response", "命名响应不可用", status_code=502)
    return cleaned

  async def _call_qwen_compatible(self, image_url: str, prompt: str) -> str:
    endpoint = self.endpoint.rstrip("/")
    if endpoint.endswith("/compatible-mode/v1"):
      endpoint = f"{endpoint}/chat/completions"

    body = {
      "model": self.model or "qwen3-vl-flash",
      "messages": [
        {
          "role": "user",
          "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": prompt},
          ],
        }
      ],
    }
    headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {self.api_key}",
      "X-DashScope-Api-Key": self.api_key,
    }

    try:
      async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(endpoint, headers=headers, json=body)
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      detail = ""
      try:
        detail = exc.response.text
      except Exception:
        detail = ""
      if status == 401:
        raise LabelGenerationError("unauthorized", f"命名服务认证失败: {detail}", status_code=401) from exc
      if status == 429:
        raise LabelGenerationError("rate_limited", f"命名服务繁忙，请稍后再试: {detail}", status_code=429) from exc
      raise LabelGenerationError("label_error", f"命名服务返回错误: {detail}", status_code=status) from exc
    except httpx.TimeoutException as exc:
      raise LabelGenerationError("timeout", "命名服务超时", status_code=504) from exc
    except Exception as exc:  # pragma: no cover - defensive
      raise LabelGenerationError("label_error", "命名服务调用失败") from exc

    data = response.json()
    text = self._extract_qwen_text(data)
    cleaned = self._clean_label(text)
    if not cleaned:
      raise LabelGenerationError("invalid_response", "命名响应不可用", status_code=502)
    return cleaned

  def _extract_text(self, data: dict) -> str:
    if isinstance(data.get("text"), str):
      return data["text"]

    candidates = data.get("candidates") or data.get("predictions") or []
    if candidates:
      first = candidates[0]
      if isinstance(first, dict):
        parts = first.get("content", {}).get("parts")
        if isinstance(parts, list):
          for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
              return part["text"]
        if isinstance(first.get("text"), str):
          return first["text"]

    if isinstance(data.get("output"), str):
      return data["output"]

    raise LabelGenerationError("invalid_response", "命名响应不可用", status_code=502)

  def _extract_qwen_text(self, data: dict) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
      first = choices[0]
      if isinstance(first, dict):
        message = first.get("message", {}) if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, list):
          for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
              return part["text"]
        if isinstance(content, str):
          return content

    output = data.get("output") or {}
    if isinstance(output, dict):
      if isinstance(output.get("text"), list) and output["text"]:
        return str(output["text"][0])
      choices = output.get("choices")
      if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
          message = first.get("message", {}) if isinstance(first.get("message"), dict) else {}
          content = message.get("content")
          if isinstance(content, list):
            for part in content:
              if isinstance(part, dict) and isinstance(part.get("text"), str):
                return part["text"]
          if isinstance(message.get("content"), str):
            return message["content"]
    if isinstance(data.get("output_text"), str):
      return data["output_text"]

    raise LabelGenerationError("invalid_response", "命名响应不可用", status_code=502)

  def _clean_label(self, text: str) -> str:
    cleaned = text.strip().splitlines()[0].strip()
    return cleaned.strip(" \"'“”‘’。,.，;；:：!！?？")
