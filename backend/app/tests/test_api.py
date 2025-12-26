import base64
import hashlib
import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ..config import get_settings
from ..dependencies import (
  get_artwork_service,
  get_detection_service,
  get_image_gen_service,
  get_text_service,
)
from ..main import create_app
from ..services.errors import DetectionError


def _make_base64_image(color=(180, 120, 80), size=(64, 48)) -> str:
  img = Image.new("RGB", size, color)
  buf = BytesIO()
  img.save(buf, format="PNG")
  return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture()
def client(tmp_path):
  storage_dir = tmp_path / "storage"
  os.environ["LOCAL_STORAGE_DIR"] = str(storage_dir)
  os.environ["IMAGE_GEN_ENDPOINT"] = ""
  os.environ["IMAGE_GEN_KEY"] = ""
  os.environ["ALIYUN_ACCESS_KEY_ID"] = ""
  os.environ["ALIYUN_ACCESS_KEY_SECRET"] = ""
  os.environ["ALIYUN_REGION"] = ""
  os.environ["ALIYUN_ENDPOINT"] = ""
  os.environ["AZURE_CV_ENDPOINT"] = ""
  os.environ["AZURE_CV_KEY"] = ""
  os.environ["TEXT_GEN_ENDPOINT"] = ""
  os.environ["TEXT_GEN_KEY"] = ""
  os.environ["SUPABASE_URL"] = ""
  os.environ["SUPABASE_KEY"] = ""

  # reset cached singletons to use the temp storage dir
  get_settings.cache_clear()
  get_detection_service.cache_clear()
  get_text_service.cache_clear()
  get_artwork_service.cache_clear()
  get_image_gen_service.cache_clear()

  app = create_app()
  test_client = TestClient(app)
  test_client.storage_dir = storage_dir
  return test_client


def test_health(client: TestClient):
  response = client.get("/health")
  assert response.status_code == 200
  assert response.json() == {"status": "ok"}


def test_detect_fallback_boxes(client: TestClient):
  img_b64 = _make_base64_image()
  response = client.post("/detect", json={"image_base64": img_b64, "max_results": 3})
  assert response.status_code == 200

  data = response.json()
  assert len(data["boxes"]) >= 1
  box = data["boxes"][0]
  assert 0 <= box["bounds"]["x"] <= 1
  assert data["image_size"]["width"] == 64
  assert data["image_size"]["height"] == 48


def test_detect_error_mapping(client: TestClient):
  class FailingDetectionService:
    async def detect(self, image_bytes, max_results):
      raise DetectionError("unauthorized", "invalid key", status_code=401)

  client.app.dependency_overrides[get_detection_service] = lambda: FailingDetectionService()
  img_b64 = _make_base64_image()
  response = client.post("/detect", json={"image_base64": img_b64, "max_results": 3})
  client.app.dependency_overrides.clear()

  assert response.status_code == 401
  assert response.json()["detail"]["code"] == "unauthorized"


def test_text_generation_fallback(client: TestClient):
  response = client.post(
    "/generate-text",
    json={"object_name": "暖黄色吊灯", "category": "家具"},
  )

  assert response.status_code == 200
  description = response.json()["description"]
  assert "暖黄色吊灯" in description
  assert len(description) <= 120


def test_image_generation_fallback(client: TestClient):
  img_b64 = _make_base64_image()
  response = client.post(
    "/generate-image",
    json={"image_base64": img_b64, "block_size": 8},
  )
  assert response.status_code == 200
  data_url = response.json()["image_base64"]
  assert data_url.startswith("data:image/png;base64,")
  raw = base64.b64decode(data_url.split(",", 1)[1])
  with Image.open(BytesIO(raw)) as img:
    assert img.size == (64, 48)


def test_save_artwork_deterministic(client: TestClient):
  img_b64 = _make_base64_image()
  payload = {
    "user_id": "user-1",
    "base_image": img_b64,
    "label": {
      "name": "暖黄色吊灯",
      "category": "菜品",
      "description": "带着暖暖香气，像刚出炉的面包。",
      "energy": 80,
      "health": 40,
      "time": {"hour": 8, "minute": 20, "month": 3, "day": 14},
      "tag_position": {"x_percent": 0.5, "y_percent": 0.6},
      "tag_scale": 1.0,
    },
    "box_bounds": {"x": 0.2, "y": 0.1, "width": 0.4, "height": 0.3},
  }

  first = client.post("/save-artwork", json=payload)
  second = client.post("/save-artwork", json=payload)

  assert first.status_code == 200
  assert second.status_code == 200

  first_data = first.json()
  second_data = second.json()

  assert first_data["checksum"] == second_data["checksum"]
  filename = f"artwork-{first_data['checksum']}.png"
  stored_path = client.storage_dir / "images" / filename
  assert stored_path.exists()

  content = stored_path.read_bytes()
  digest = hashlib.sha256(content).hexdigest()
  assert digest == first_data["checksum"]

  with Image.open(BytesIO(content)) as img:
    assert img.size == (64, 48)

  list_response = client.get("/artworks")
  assert list_response.status_code == 200
  data = list_response.json()
  items = data["items"]
  assert len(items) >= 1
  assert items[0]["url"] == first_data["url"]
  assert data.get("total") is None or data["total"] >= len(items)

  paged = client.get("/artworks?limit=1&offset=1")
  assert paged.status_code == 200
