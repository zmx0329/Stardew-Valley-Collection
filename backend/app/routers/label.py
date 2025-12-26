from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_label_service
from ..models.label import LabelRequest, LabelResponse
from ..services.errors import LabelGenerationError
from ..services.label_service import LabelService

router = APIRouter()


@router.post("/generate-label", response_model=LabelResponse)
async def generate_label(
  payload: LabelRequest, service: LabelService = Depends(get_label_service)
) -> LabelResponse:
  try:
    return await service.generate_label(payload)
  except LabelGenerationError as exc:
    raise HTTPException(status_code=exc.status_code or 502, detail={"code": exc.code, "message": exc.message}) from exc
