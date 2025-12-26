from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from ..models.common import ArtworkRecord
from ..services.errors import StorageError


class LocalStorageClient:
  """Simple filesystem-backed storage used for local dev and tests."""

  def __init__(self, base_dir: Path):
    self.base_dir = Path(base_dir)
    self.images_dir = self.base_dir / "images"
    self.records_file = self.base_dir / "records.json"
    self.images_dir.mkdir(parents=True, exist_ok=True)
    if not self.records_file.exists():
      self.records_file.write_text("[]", encoding="utf-8")

  async def upload_image(self, filename: str, data: bytes, content_type: str = "image/png") -> str:
    try:
      path = self.images_dir / filename
      path.write_bytes(data)
      return f"local://artworks/{filename}"
    except Exception as exc:  # pragma: no cover - defensive
      raise StorageError("local_write_failed", "无法写入本地存储") from exc

  async def save_record(self, record: ArtworkRecord) -> None:
    records = self._load_records()
    records.append(record)
    self.records_file.write_text(
      json.dumps([r.model_dump(mode="json") for r in records], ensure_ascii=False), encoding="utf-8"
    )

  async def list_records(self, limit: int = 20, offset: int = 0) -> List[ArtworkRecord]:
    records = self._load_records()
    sorted_records = sorted(records, key=lambda r: r.created_at, reverse=True)
    return sorted_records[offset : offset + limit]

  async def count_records(self) -> int:
    return len(self._load_records())

  def _load_records(self) -> List[ArtworkRecord]:
    raw = self.records_file.read_text(encoding="utf-8")
    if not raw.strip():
      return []
    data = json.loads(raw)
    records: list[ArtworkRecord] = []
    for item in data:
      try:
        records.append(
          ArtworkRecord(
            id=item["id"],
            user_id=item["user_id"],
            url=item["url"],
            created_at=datetime.fromisoformat(item["created_at"]),
          )
        )
      except Exception:
        continue
    return records


class SupabaseStorageClient:
  """Supabase-backed storage. Only instantiated when credentials are present."""

  def __init__(self, url: str, key: str, bucket: str, table: str):
    try:
      from supabase import create_client
    except ImportError as exc:  # pragma: no cover - library missing
      raise StorageError("supabase_import", "缺少 supabase 依赖") from exc

    normalized_url = url if url.endswith("/") else f"{url}/"
    self.client = create_client(normalized_url, key)
    self.bucket = bucket
    self.table = table

  async def upload_image(self, filename: str, data: bytes, content_type: str = "image/png") -> str:
    try:
      self.client.storage.from_(self.bucket).upload(
        filename,
        data,
        {"content-type": content_type, "upsert": "true"},
      )
      public_url = self.client.storage.from_(self.bucket).get_public_url(filename)
      return public_url
    except Exception as exc:  # pragma: no cover - network path not exercised in tests
      raise StorageError("supabase_upload_failed", f"Supabase 上传失败: {exc}") from exc

  async def save_record(self, record: ArtworkRecord) -> None:
    try:
      self.client.table(self.table).insert(record.model_dump(mode="json")).execute()
    except Exception as exc:  # pragma: no cover
      raise StorageError("supabase_insert_failed", f"Supabase 记录写入失败: {exc}") from exc

  async def list_records(self, limit: int = 20, offset: int = 0) -> List[ArtworkRecord]:
    try:
      start = max(0, offset)
      end = max(start, start + max(1, limit) - 1)
      response = (
        self.client.table(self.table)
        .select("*")
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
      )
      items = response.data or []
      return [
        ArtworkRecord(
          id=item["id"],
          user_id=item["user_id"],
          url=item["url"],
          created_at=datetime.fromisoformat(item["created_at"]),
        )
        for item in items
      ]
    except Exception as exc:  # pragma: no cover
      raise StorageError("supabase_list_failed", "Supabase 读取失败") from exc

  async def count_records(self) -> int:
    try:
      response = self.client.table(self.table).select("id", count="exact").execute()
      return response.count or 0
    except Exception as exc:  # pragma: no cover
      raise StorageError("supabase_count_failed", "Supabase 计数失败") from exc
