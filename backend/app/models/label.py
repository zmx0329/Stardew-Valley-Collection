from pydantic import BaseModel, ConfigDict

from .common import NormalizedBounds


class LabelRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  image_base64: str
  bounds: NormalizedBounds
  hint: str | None = None


class LabelResponse(BaseModel):
  model_config = ConfigDict(extra="forbid")

  label: str
