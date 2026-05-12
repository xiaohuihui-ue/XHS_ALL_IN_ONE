import base64

from backend.app.models import ModelConfig
from backend.app.services.ai_service import OpenAICompatibleImageClient


def test_image_reference_file_url_resolves_to_data_url(tmp_path):
    image_file = tmp_path / "reference.png"
    image_bytes = b"fake-png-bytes"
    image_file.write_bytes(image_bytes)

    resolved = OpenAICompatibleImageClient._resolve_image_ref(f"file://{image_file}")

    assert resolved == f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"


def test_generate_image_resolves_reference_file_before_request(tmp_path, monkeypatch):
    image_file = tmp_path / "reference.png"
    image_bytes = b"fake-png-bytes"
    image_file.write_bytes(image_bytes)
    captured_request = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"url": "https://cdn.example.test/generated.png"}]}

    def fake_post(url, *, headers, json, timeout):
        captured_request.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("backend.app.services.ai_service.requests.post", fake_post)

    result = OpenAICompatibleImageClient().generate_image(
        model_config=ModelConfig(
            model_name="image-model",
            base_url="https://api.example.test/v1",
        ),
        api_key="sk-test",
        prompt="仿图生成",
        reference_images=[f"file://{image_file}"],
    )

    assert result["url"] == "https://cdn.example.test/generated.png"
    assert captured_request["url"] == "https://api.example.test/v1/images/generations"
    assert captured_request["json"]["image"] == f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
