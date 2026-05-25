from __future__ import annotations

from backend.app.models import ModelConfig
from backend.app.services.ai_service import (
    AOMENT_API_BASE_URL,
    AomentImageClient,
    ImageModelAdapterClient,
)


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_aoment_text_to_image_uses_fixed_base_url_and_polls_record(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, *, headers=None, json=None, data=None, files=None, timeout=None):
        calls.append({"method": "POST", "url": url, "headers": headers, "json": json, "data": data, "files": files, "timeout": timeout})
        return _FakeResponse({"success": True, "recordId": "api_task_1", "status": "processing"})

    def fake_get(url, *, headers=None, timeout=None):
        calls.append({"method": "GET", "url": url, "headers": headers, "timeout": timeout})
        return _FakeResponse({"success": True, "recordId": "api_task_1", "status": "success", "imageUrl": "https://cos.example.com/result.jpg"})

    monkeypatch.setattr("backend.app.services.ai_service.requests.post", fake_post)
    monkeypatch.setattr("backend.app.services.ai_service.requests.get", fake_get)

    result = AomentImageClient(poll_interval_seconds=0, max_poll_attempts=1).generate_image(
        model_config=ModelConfig(provider="aoment", model_name="image-o2-pro", base_url=""),
        api_key="aoment_test_key",
        prompt="warm modern living room",
    )

    assert result["url"] == "https://cos.example.com/result.jpg"
    assert calls[0]["url"] == f"{AOMENT_API_BASE_URL}/image/generations"
    assert calls[0]["headers"] == {"Authorization": "Bearer aoment_test_key", "Content-Type": "application/json"}
    assert calls[0]["json"] == {
        "prompt": "warm modern living room",
        "model": "image-o2-pro",
        "aspectRatio": "1:1",
        "imageSize": "2K",
        "showInWebCreating": False,
    }
    assert calls[1]["url"] == f"{AOMENT_API_BASE_URL}/records/api_task_1"


def test_aoment_image_to_image_uses_multipart_images(tmp_path, monkeypatch):
    image_file = tmp_path / "reference.png"
    image_file.write_bytes(b"fake-image")
    captured: dict = {}

    def fake_post(url, *, headers=None, json=None, data=None, files=None, timeout=None):
        captured.update({"url": url, "headers": headers, "json": json, "data": data, "files": files, "timeout": timeout})
        return _FakeResponse({"success": True, "recordId": "api_task_2", "status": "processing"})

    def fake_get(url, *, headers=None, timeout=None):
        return _FakeResponse({"success": True, "recordId": "api_task_2", "status": "success", "imageUrl": "https://cos.example.com/edited.jpg"})

    monkeypatch.setattr("backend.app.services.ai_service.requests.post", fake_post)
    monkeypatch.setattr("backend.app.services.ai_service.requests.get", fake_get)

    result = AomentImageClient(poll_interval_seconds=0, max_poll_attempts=1).generate_image(
        model_config=ModelConfig(provider="aoment", model_name="image-o2-pro", base_url=""),
        api_key="aoment_test_key",
        prompt="keep layout, change to Japandi interior",
        reference_images=[f"file://{image_file}"],
    )

    assert result["url"] == "https://cos.example.com/edited.jpg"
    assert captured["url"] == f"{AOMENT_API_BASE_URL}/image/generations"
    assert captured["headers"] == {"Authorization": "Bearer aoment_test_key"}
    assert captured["json"] is None
    assert captured["data"]["prompt"] == "keep layout, change to Japandi interior"
    assert captured["data"]["model"] == "image-o2-pro"
    assert captured["data"]["showInWebCreating"] == "false"
    assert captured["files"][0][0] == "images"
    assert captured["files"][0][1][0] == "reference.png"
    assert captured["files"][0][1][1] == b"fake-image"
    assert captured["files"][0][1][2] == "image/png"


def test_aoment_image_recognition_returns_result_text(tmp_path, monkeypatch):
    image_file = tmp_path / "room.jpg"
    image_file.write_bytes(b"fake-jpeg")
    captured: dict = {}

    def fake_post(url, *, headers=None, json=None, data=None, files=None, timeout=None):
        captured.update({"url": url, "headers": headers, "json": json, "data": data, "files": files, "timeout": timeout})
        return _FakeResponse({"success": True, "resultText": "A warm living room with wood tones."})

    monkeypatch.setattr("backend.app.services.ai_service.requests.post", fake_post)

    text = AomentImageClient(poll_interval_seconds=0, max_poll_attempts=1).describe_image(
        model_config=ModelConfig(provider="aoment", model_name="image-o2-pro", base_url=""),
        api_key="aoment_test_key",
        image_url=f"file://{image_file}",
        instruction="describe this room",
    )

    assert text == "A warm living room with wood tones."
    assert captured["url"] == f"{AOMENT_API_BASE_URL}/image/recognitions"
    assert captured["headers"] == {"Authorization": "Bearer aoment_test_key"}
    assert captured["data"] == {"prompt": "describe this room", "model": "image-to-text"}
    assert captured["files"][0][0] == "images"


def test_image_model_adapter_routes_aoment_provider(monkeypatch):
    captured: dict = {}

    def fake_post(url, *, headers=None, json=None, data=None, files=None, timeout=None):
        captured["url"] = url
        return _FakeResponse({"success": True, "recordId": "api_task_3", "status": "processing"})

    def fake_get(url, *, headers=None, timeout=None):
        return _FakeResponse({"success": True, "recordId": "api_task_3", "status": "success", "imageUrl": "https://cos.example.com/result.jpg"})

    monkeypatch.setattr("backend.app.services.ai_service.requests.post", fake_post)
    monkeypatch.setattr("backend.app.services.ai_service.requests.get", fake_get)

    result = ImageModelAdapterClient(
        aoment_client=AomentImageClient(poll_interval_seconds=0, max_poll_attempts=1)
    ).generate_image(
        model_config=ModelConfig(provider="aoment", model_name="image-n2-fast", base_url=""),
        api_key="aoment_test_key",
        prompt="living room",
    )

    assert result["url"] == "https://cos.example.com/result.jpg"
    assert captured["url"] == f"{AOMENT_API_BASE_URL}/image/generations"
