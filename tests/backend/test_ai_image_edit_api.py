from unittest.mock import MagicMock
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.ai import get_image_ai_client
from backend.app.core.database import Base, get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import encrypt_text
from backend.app.main import app
from backend.app.models import ModelConfig, User
from backend.app.schemas.image_edit import HOME_DECOR_CHECK_NAMES


def _override_app(tmp_path, *, image_client, image_capabilities=None):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    user = User(username="image-editor", email="image-editor@test.com", password_hash="x")
    db.add(user)
    db.flush()
    db.add(
        ModelConfig(
            user_id=user.id,
            name="default-image",
            model_type="image",
            provider="openai",
            model_name="image-test",
            base_url="http://fake-image",
            encrypted_api_key=encrypt_text("sk-image"),
            is_default=True,
            capabilities=image_capabilities or ["image_generation", "image_edit"],
        )
    )
    db.commit()
    db.refresh(user)
    db.close()

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_image_ai_client] = lambda: image_client
    return engine, SessionLocal


def _cleanup(engine, SessionLocal):
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_image_ai_client, None)
    SessionLocal.close_all()
    engine.dispose()


def test_ai_image_edit_returns_structured_home_decor_artifact(tmp_path):
    image_client = MagicMock()
    image_client.generate_image.return_value = {
        "url": "data:image/png;base64,abc",
        "raw": {"id": "img-response"},
    }
    engine, SessionLocal = _override_app(tmp_path, image_client=image_client)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/ai/images/edit",
            json={
                "model": "image-test",
                "source_images": [
                    {"id": "room-1", "role": "source_room", "url": "https://cdn.example.com/room.jpg"}
                ],
                "task_type": "room_makeover",
                "domain": "home_decor",
                "edit_intent": "Make a warm modern cream living room for a Xiaohongshu cover.",
                "preserve": ["window position", "ceiling height"],
                "change": ["sofa", "wall color"],
                "avoid": ["dark tones", "text in image"],
                "output_goal": "xhs_cover",
                "realism_level": "high",
                "room_type": "living_room",
                "decor_style": "modern_cream",
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
                "style": "natural",
                "response_format": "url",
                "save_to_assets": False,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["request_id"]
        assert body["status"] == "completed"
        assert body["source_images"][0]["url"] == "https://cdn.example.com/room.jpg"
        assert body["normalized_spec"]["domain"] == "home_decor"
        assert body["edit_plan"]["layout_policy"] == "Preserve: window position, ceiling height"
        assert "warm modern cream living room" in body["compiled_prompts"]["positive_prompt"]
        assert "dark tones" in body["compiled_prompts"]["negative_prompt"]
        assert body["result_assets"][0]["url"] == "data:image/png;base64,abc"
        assert body["quality_report"]["passed"] is True
        assert {item["name"] for item in body["quality_report"]["checks"]} == set(HOME_DECOR_CHECK_NAMES)
        assert body["provenance"]["model_name"] == "image-test"
        assert body["provenance"]["knowledge_base"] == "home_decor_v1"
        assert body["report"]["file_name"].startswith("xhs-image-report-u")
        assert body["report"]["download_url"].startswith("/api/files/exports/")
        report_path = Path(body["report"]["file_path"])
        assert report_path.is_file()
        report_html = report_path.read_text(encoding="utf-8")
        assert "Interior Design Image Report" in report_html
        assert "https://cdn.example.com/room.jpg" in report_html
        assert "Make a warm modern cream living room" in report_html
        assert "structure_preserved" in report_html
        assert "modern_cream" in report_html
        assert "data:image/png;base64,abc" in report_html
        download_response = client.get(body["report"]["download_url"])
        assert download_response.status_code == 200
        assert "text/html" in download_response.headers["content-type"]
        assert "Interior Design Image Report" in download_response.text

        image_client.generate_image.assert_called_once()
        call_kwargs = image_client.generate_image.call_args.kwargs
        assert call_kwargs["prompt"] == body["compiled_prompts"]["positive_prompt"]
        assert call_kwargs["reference_images"] == ["https://cdn.example.com/room.jpg"]
        assert call_kwargs["size"] == "1792x1024"
        assert call_kwargs["quality"] == "hd"
        assert call_kwargs["style"] == "natural"
        assert call_kwargs["response_format"] == "url"
    finally:
        _cleanup(engine, SessionLocal)


def test_ai_image_edit_rejects_empty_source_images(tmp_path):
    image_client = MagicMock()
    engine, SessionLocal = _override_app(tmp_path, image_client=image_client)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/ai/images/edit",
            json={
                "source_images": [],
                "task_type": "room_makeover",
                "domain": "home_decor",
                "edit_intent": "Make a warm living room.",
            },
        )

        assert response.status_code == 422
        image_client.generate_image.assert_not_called()
    finally:
        _cleanup(engine, SessionLocal)


def test_ai_image_edit_requires_image_edit_capability(tmp_path):
    image_client = MagicMock()
    engine, SessionLocal = _override_app(
        tmp_path,
        image_client=image_client,
        image_capabilities=["image_generation"],
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/api/ai/images/edit",
            json={
                "source_images": [
                    {"id": "room-1", "role": "source_room", "url": "https://cdn.example.com/room.jpg"}
                ],
                "task_type": "room_makeover",
                "domain": "home_decor",
                "edit_intent": "Make a warm living room.",
            },
        )

        assert response.status_code == 400
        assert "image_edit" in response.json()["detail"]
        image_client.generate_image.assert_not_called()
    finally:
        _cleanup(engine, SessionLocal)
