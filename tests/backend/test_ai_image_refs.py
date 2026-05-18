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
        status_code = 200
        content = b""
        text = ""

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


def test_generate_image_forwards_openai_image_options(monkeypatch):
    captured_request = {}

    class FakeResponse:
        status_code = 200
        content = b""
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"b64_json": "encoded-image"}]}

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
        prompt="生成室内设计图",
        size="1792x1024",
        quality="hd",
        style="natural",
        response_format="b64_json",
    )

    assert result["url"] == "encoded-image"
    assert captured_request["json"]["size"] == "1792x1024"
    assert captured_request["json"]["quality"] == "hd"
    assert captured_request["json"]["style"] == "natural"
    assert captured_request["json"]["response_format"] == "b64_json"
