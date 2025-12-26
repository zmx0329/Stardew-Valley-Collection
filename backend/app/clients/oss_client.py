from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import anyio

from ..services.errors import StorageError


class OssStorageClient:
  """Minimal OSS uploader for detection images."""

  def __init__(
    self,
    endpoint: str,
    bucket: str,
    access_key_id: str,
    access_key_secret: str,
    public_base_url: Optional[str] = None,
  ) -> None:
    if not (endpoint and bucket and access_key_id and access_key_secret):
      raise StorageError("oss_config", "未配置 OSS")

    try:
      import oss2  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
      raise StorageError("oss_import", "缺少 OSS 依赖") from exc

    normalized_endpoint = endpoint.strip().rstrip("/")
    if not normalized_endpoint:
      raise StorageError("oss_config", "未配置 OSS Endpoint")

    parsed = urlparse(normalized_endpoint)
    if not parsed.scheme:
      normalized_endpoint = f"https://{normalized_endpoint}"
      parsed = urlparse(normalized_endpoint)

    host = parsed.netloc or parsed.path
    is_cname = host.startswith(f"{bucket}.")

    auth = oss2.Auth(access_key_id, access_key_secret)
    self.bucket = oss2.Bucket(auth, normalized_endpoint, bucket, is_cname=is_cname)

    if public_base_url:
      self.public_base_url = public_base_url.rstrip("/")
    elif is_cname:
      self.public_base_url = normalized_endpoint.rstrip("/")
    else:
      self.public_base_url = f"{parsed.scheme}://{bucket}.{host}".rstrip("/")

  async def upload_image(self, key: str, data: bytes, content_type: str = "image/png") -> str:
    headers = {"Content-Type": content_type, "x-oss-object-acl": "public-read"}
    try:
      result = await anyio.to_thread.run_sync(self.bucket.put_object, key, data, headers)
    except Exception as exc:  # pragma: no cover - network path
      detail = getattr(exc, "details", None)
      if detail:
        raise StorageError("oss_upload_failed", f"OSS 上传失败: {detail}") from exc
      raise StorageError("oss_upload_failed", f"OSS 上传失败: {exc}") from exc

    status = getattr(result, "status", None)
    if status not in (200, 201):
      raise StorageError("oss_upload_failed", f"OSS 上传失败: status={status}")

    return f"{self.public_base_url}/{key}"
