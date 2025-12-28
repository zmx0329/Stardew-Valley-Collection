from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NormalizedBounds(BaseModel):
  model_config = ConfigDict(extra="forbid")

  x: float = Field(ge=0, le=1)
  y: float = Field(ge=0, le=1)
  width: float = Field(gt=0, le=1)
  height: float = Field(gt=0, le=1)


class ImageSize(BaseModel):
  model_config = ConfigDict(extra="forbid")

  width: int = Field(gt=0)
  height: int = Field(gt=0)


class DetectionBox(BaseModel):
  model_config = ConfigDict(extra="forbid")

  id: str
  bounds: NormalizedBounds
  label: Optional[str] = None
  confidence: Optional[float] = Field(default=None, ge=0, le=1)


class TimePayload(BaseModel):
  model_config = ConfigDict(extra="forbid")

  hour: int = Field(ge=0, le=23)
  minute: int = Field(ge=0, le=59)
  month: int = Field(ge=1, le=12)
  day: int = Field(ge=1, le=31)


class TagPosition(BaseModel):
  model_config = ConfigDict(extra="forbid")

  x_percent: float = Field(ge=0, le=1)
  y_percent: float = Field(ge=0, le=1)


class LabelPayload(BaseModel):
  model_config = ConfigDict(extra="forbid")

  name: str
  category: str
  description: str
  energy: int = Field(ge=0, le=200)
  health: int = Field(ge=0, le=200)
  time: TimePayload
  tag_position: TagPosition
  tag_scale: float = Field(default=1.0, gt=0, le=3.0)


class ArtworkRecord(BaseModel):
  model_config = ConfigDict(extra="forbid")

  id: str
  user_id: str
  name: str | None = None
  url: str
  created_at: datetime
