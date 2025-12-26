from pydantic import BaseModel, ConfigDict, Field


class ImageGenRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  image_base64: str = Field(description="Base64 image data URL or raw base64")
  prompt: str | None = Field(default=None, description="Optional style prompt")
  block_size: int = Field(default=10, ge=2, le=64, description="Fallback pixel block size")


class ImageGenResponse(BaseModel):
  model_config = ConfigDict(extra="forbid")

  image_base64: str
  source: str | None = Field(default=None, description="remote or fallback")
  note: str | None = Field(default=None, description="optional warning when fallback is used")
