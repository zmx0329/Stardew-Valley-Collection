from __future__ import annotations

import httpx

from ..services.errors import TextGenerationError


class LLMTextClient:
  """Generic LLM text generation client."""

  def __init__(self, endpoint: str, api_key: str, model: str | None = None, provider: str = "generic"):
    self.endpoint = endpoint
    self.api_key = api_key
    self.model = model
    self.provider = (provider or "generic").lower()

  async def generate_description(self, object_name: str, category: str, context: str | None = None) -> str:
    if not self.endpoint or not self.api_key:
      raise TextGenerationError("llm_config", "未配置文案服务", status_code=500)

    prompt = self._build_prompt(object_name, category, context)

    if self.provider == "qwen" or "dashscope.aliyuncs.com/compatible-mode" in self.endpoint:
      return await self._call_qwen(prompt)

    payload = {
      "object_name": object_name,
      "category": category,
      "context": context,
      "tone": "stardew",
      "prompt": prompt,
    }
    headers = {"Authorization": f"Bearer {self.api_key}"}

    data = await self._post_json(self.endpoint, payload, headers)
    text = self._extract_text(data)
    if not text:
      raise TextGenerationError("invalid_response", "文案服务响应不可用", status_code=502)
    return text

  async def _call_qwen(self, prompt: str) -> str:
    endpoint = self.endpoint.rstrip("/")
    if endpoint.endswith("/compatible-mode/v1"):
      endpoint = f"{endpoint}/chat/completions"
    body = {
      "model": self.model or "qwen-plus",
      "messages": [
        {"role": "system", "content": "你是星露谷物语的道具文案助手。"},
        {"role": "user", "content": prompt},
      ],
      "temperature": 0.7,
    }
    headers = {
      "Authorization": f"Bearer {self.api_key}",
      "X-DashScope-Api-Key": self.api_key,
      "Content-Type": "application/json",
    }

    data = await self._post_json(endpoint, body, headers)
    text = self._extract_text(data)
    if not text:
      raise TextGenerationError("invalid_response", "文案服务响应不可用", status_code=502)
    return text

  def _build_prompt(self, object_name: str, category: str, context: str | None) -> str:
    context_line = f"补充信息：{context}" if context else "补充信息：无"
    return (
      "你是《星露谷物语》世界的物品描述写作者。根据物品名称与类别，生成 1–2 句中文描述，必须是30字以内，含一个物品功能描写 + 一个轻微的情绪/联想。"
      "语气温暖、朴实、乡村生活感强。避免空泛和夸张，不要捏造不存在的功能；"
      "可以点到为止地提及季节、用途。不要具体描述物品的具体形态颜色图案等。可以提及星露谷中真实存在的人物地点，不可捏造人物名称和地点。仅输出纯文本，不要列表、不要引号。"
      f"\n物品名称：{object_name}\n类别：{category}\n{context_line}"
    )

  async def _post_json(self, endpoint: str, payload: dict, headers: dict) -> dict:
    async with httpx.AsyncClient(timeout=12.0) as client:
      try:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
      except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
          raise TextGenerationError("unauthorized", "文案服务认证失败", status_code=401) from exc
        if status == 429:
          raise TextGenerationError("rate_limited", "文案服务繁忙，请稍后再试", status_code=429) from exc
        raise TextGenerationError("llm_error", "文案服务返回错误", status_code=status) from exc
      except httpx.TimeoutException as exc:
        raise TextGenerationError("timeout", "文案生成超时", status_code=504) from exc

    return response.json()

  def _extract_text(self, data: dict) -> str | None:
    if "description" in data and isinstance(data["description"], str):
      return data["description"].strip()
    if "text" in data and isinstance(data["text"], str):
      return data["text"].strip()
    choices = data.get("choices")
    if choices and isinstance(choices, list):
      first = choices[0]
      if isinstance(first, dict):
        message = first.get("message", {}) if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str):
          return content.strip()

    return None
