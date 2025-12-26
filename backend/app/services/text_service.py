from __future__ import annotations

import re

from ..clients.text_client import LLMTextClient
from ..config import Settings
from ..models.text import TextRequest, TextResponse
from .errors import TextGenerationError


class TextService:
  """Generates Stardew-toned descriptions with LLM + safe fallback."""

  def __init__(self, settings: Settings):
    self.settings = settings
    provider = (settings.text_gen_provider or "auto").lower()
    endpoint = settings.text_gen_endpoint
    key = settings.text_gen_key
    model = settings.text_gen_model

    if provider == "auto":
      if endpoint and key:
        self.client = LLMTextClient(endpoint, key, model, provider="generic")
      elif settings.label_gen_provider.lower() == "qwen" and settings.label_gen_endpoint and settings.label_gen_key:
        self.client = LLMTextClient(settings.label_gen_endpoint, settings.label_gen_key, model, provider="qwen")
      else:
        self.client = None
    else:
      if provider == "qwen" and not endpoint:
        endpoint = settings.label_gen_endpoint
      if provider == "qwen" and not key:
        key = settings.label_gen_key
      self.client = LLMTextClient(endpoint or "", key or "", model, provider=provider) if endpoint and key else None

  async def generate_description(self, request: TextRequest) -> TextResponse:
    object_name = request.object_name or "这件物品"
    category = request.category or "杂物"
    context = request.context

    if self.client:
      try:
        text = await self.client.generate_description(object_name, category, context)
        trimmed = self._trim_to_two_sentences(text)
        return TextResponse(description=self._limit_length(trimmed, 50))
      except (TextGenerationError, Exception):
        # Fallback to template on any upstream failure (429/timeout/invalid response/网络不可达)
        pass

    fallback = self._template_description(object_name, category, context)
    return TextResponse(description=self._limit_length(fallback, 50))

  def _template_description(self, object_name: str, category: str, context: str | None) -> str:
    hint = "像是从谷仓里翻出的旧物" if category in ("杂物", "家具") else "带着刚晒过的暖意"
    context_note = f"像{context}" if context else "带着星露谷的慢日子"
    return f"{object_name}{hint}，{context_note}。"

  def _trim_to_two_sentences(self, text: str) -> str:
    """Ensure the result stays short (<=2 sentences)."""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
      return self._template_description("这件物品", "杂物", None)
    boundaries = list(re.finditer(r"[。！？.!?]", normalized))
    if len(boundaries) >= 2:
      return normalized[:boundaries[1].end()]
    if len(boundaries) == 1:
      return normalized[:boundaries[0].end()]
    return normalized

  def _limit_length(self, text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
      return text
    shortened = text[:max_chars].rstrip()
    if shortened and shortened[-1] not in "。！？.!?":
      shortened = shortened[: max(0, max_chars - 1)].rstrip() + "。"
    return shortened
