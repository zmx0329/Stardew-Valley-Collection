from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import artworks, detect, health, text_gen, image_gen, label


def create_app() -> FastAPI:
  settings = get_settings()
  app = FastAPI(title="Memory Bank Backend", version="0.1.0")

  app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )

  app.include_router(health.router)
  app.include_router(detect.router)
  app.include_router(text_gen.router)
  app.include_router(image_gen.router)
  app.include_router(label.router)
  app.include_router(artworks.router)

  @app.get("/config/storage")
  async def storage_mode() -> dict[str, str]:
    mode = "local" if settings.use_local_storage else "supabase"
    return {"mode": mode}

  @app.get("/config/image-gen")
  async def image_gen_mode() -> dict[str, object]:
    endpoint = settings.image_gen_endpoint or ""
    model = settings.image_gen_model or ""
    configured = bool(endpoint and settings.image_gen_key)
    use_qwen = "dashscope.aliyuncs.com" in endpoint or model.startswith("qwen-")
    provider = "qwen" if use_qwen else "gemini"
    public_storage_configured = bool(
      (
        settings.oss_endpoint
        and settings.oss_bucket
        and (settings.oss_access_key_id or settings.aliyun_access_key_id)
        and (settings.oss_access_key_secret or settings.aliyun_access_key_secret)
      )
      or (settings.supabase_url and settings.supabase_key)
    )
    requires_public_url = use_qwen
    can_remote = configured and (not requires_public_url or public_storage_configured)

    warnings: list[str] = []
    if not configured:
      warnings.append("missing_image_gen_config")
    if requires_public_url and not public_storage_configured:
      warnings.append("missing_public_storage")

    return {
      "configured": configured,
      "provider": provider,
      "model": model or None,
      "requires_public_url": requires_public_url,
      "public_storage_configured": public_storage_configured,
      "expected_mode": "remote" if can_remote else "fallback",
      "warnings": warnings,
    }

  return app


app = create_app()
