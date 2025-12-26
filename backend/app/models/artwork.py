from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .common import ArtworkRecord, LabelPayload, NormalizedBounds


class SaveArtworkRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  user_id: str
  base_image: str = Field(description="Base64 encoded pixel-style image (data URL allowed)")
  composed_image: str | None = Field(
    default=None, description="Optional fully composed preview image to persist as-is"
  )
  label: LabelPayload
  box_bounds: NormalizedBounds | None = Field(
    default=None, description="Normalized bounds of the selected object to mirror preview layout"
  )


class SaveArtworkResponse(BaseModel):
  model_config = ConfigDict(extra="forbid")

  id: str
  url: str
  created_at: datetime
  checksum: str


class ArtworksResponse(BaseModel):
  model_config = ConfigDict(extra="forbid")

  items: list[ArtworkRecord]
  total: int | None = None
