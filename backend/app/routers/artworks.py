from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_artwork_service
from ..models.artwork import ArtworksResponse, SaveArtworkRequest, SaveArtworkResponse
from ..services.artwork_service import ArtworkService
from ..services.errors import ImageGenerationError, StorageError

router = APIRouter()


@router.post("/save-artwork", response_model=SaveArtworkResponse)
async def save_artwork(
  payload: SaveArtworkRequest, service: ArtworkService = Depends(get_artwork_service)
) -> SaveArtworkResponse:
  try:
    return await service.save_artwork(payload)
  except ImageGenerationError as exc:
    raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
  except StorageError as exc:
    raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/artworks", response_model=ArtworksResponse)
async def list_artworks(
  limit: int = Query(20, ge=1, le=50),
  offset: int = Query(0, ge=0),
  service: ArtworkService = Depends(get_artwork_service),
) -> ArtworksResponse:
  return await service.list_artworks(limit, offset)
