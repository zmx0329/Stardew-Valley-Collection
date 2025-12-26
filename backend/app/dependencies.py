from functools import lru_cache

from .config import Settings, get_settings
from .services.artwork_service import ArtworkService
from .services.detection_service import DetectionService
from .services.image_gen_service import ImageGenerationService
from .services.label_service import LabelService
from .services.text_service import TextService


def get_settings_dep() -> Settings:
  return get_settings()


@lru_cache(maxsize=1)
def get_detection_service() -> DetectionService:
  return DetectionService(get_settings())


@lru_cache(maxsize=1)
def get_text_service() -> TextService:
  return TextService(get_settings())


@lru_cache(maxsize=1)
def get_artwork_service() -> ArtworkService:
  return ArtworkService(get_settings())


@lru_cache(maxsize=1)
def get_image_gen_service() -> ImageGenerationService:
  return ImageGenerationService(get_settings())


@lru_cache(maxsize=1)
def get_label_service() -> LabelService:
  return LabelService(get_settings())
