from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ..clients.storage_client import LocalStorageClient, SupabaseStorageClient
from ..config import Settings
from ..models.artwork import ArtworksResponse, SaveArtworkRequest, SaveArtworkResponse
from ..models.common import ArtworkRecord
from .image_service import ImageService
from .utils import decode_base64_image


class ArtworkService:
  """Handles artwork composition and persistence."""

  def __init__(self, settings: Settings):
    self.settings = settings
    self.image_service = ImageService()
    self.storage_client = (
      LocalStorageClient(settings.local_storage_dir)
      if settings.use_local_storage
      else SupabaseStorageClient(settings.supabase_url or "", settings.supabase_key or "", settings.supabase_bucket, settings.supabase_table)
    )

  async def save_artwork(self, payload: SaveArtworkRequest) -> SaveArtworkResponse:
    if payload.composed_image:
      composed = decode_base64_image(payload.composed_image)
    else:
      base_image_bytes = decode_base64_image(payload.base_image)
      composed = self.image_service.compose(base_image_bytes, payload.label, payload.box_bounds)

    checksum = hashlib.sha256(composed).hexdigest()
    filename = f"artwork-{checksum}.png"
    url = await self.storage_client.upload_image(filename, composed)

    record_id = checksum[:16]
    record = ArtworkRecord(id=record_id, user_id=payload.user_id, url=url, created_at=datetime.now(timezone.utc))
    await self.storage_client.save_record(record)

    return SaveArtworkResponse(id=record_id, url=url, created_at=record.created_at, checksum=checksum)

  async def list_artworks(self, limit: int = 20, offset: int = 0) -> ArtworksResponse:
    items = await self.storage_client.list_records(limit, offset)
    total = None
    try:
      total = await self.storage_client.count_records()
    except Exception:
      total = None
    return ArtworksResponse(items=items, total=total)
