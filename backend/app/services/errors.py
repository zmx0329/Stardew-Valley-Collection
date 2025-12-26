class ServiceError(Exception):
  def __init__(self, code: str, message: str, status_code: int = 500) -> None:
    super().__init__(message)
    self.code = code
    self.status_code = status_code
    self.message = message


class DetectionError(ServiceError):
  pass


class TextGenerationError(ServiceError):
  pass


class ImageGenerationError(ServiceError):
  pass


class LabelGenerationError(ServiceError):
  pass


class StorageError(ServiceError):
  pass
