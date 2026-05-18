import json
import pytest
from unittest.mock import MagicMock, patch
from backend.app.services.ai_service import OpenAICompatibleTextClient
from backend.app.models import ModelConfig


def _make_model_config(base_url="http://fake-llm", model_name="gpt-test", capabilities=None):
    cfg = ModelConfig()
    cfg.model_type = "text"
    cfg.base_url = base_url
    cfg.model_name = model_name
    if capabilities is not None:
        cfg.capabilities = capabilities
    return cfg


VALID_SCHEMA_RESPONSE = {
    "drafts": [
        {
            "title": "低卡早餐推荐",
            "body": "这款早餐热量低，口感好。",
            "tags": ["低卡早餐", "健康饮食"],
            "image_prompt": {
                "positive_prompt": "healthy breakfast bowl, bright natural light",
                "negative_prompt": "unhealthy food, dark",
                "reference_strategy": "use_reference_images",
            },
        }
    ]
}


def _mock_response(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.raise_for_status = MagicMock()
    return r


def test_generate_agent_drafts_pass1_success():
    """Pass 1 succeeds when provider returns valid JSON content."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config(capabilities=["text_generation", "vision"])
    messages = [{"role": "user", "content": "Generate 1 draft."}]

    api_response = {
        "choices": [{"message": {"content": json.dumps(VALID_SCHEMA_RESPONSE)}}]
    }
    with patch("requests.post", return_value=_mock_response(api_response)):
        result = client.generate_agent_drafts(
            model_config=cfg,
            api_key="sk-test",
            messages=messages,
            n=1,
            temperature=0.7,
            top_p=1.0,
            output_requirements=None,
            reference_image_urls=[],
        )
    assert "drafts" in result
    assert result["drafts"][0]["title"] == "低卡早餐推荐"


def test_generate_agent_drafts_pass2_fallback_on_bad_json():
    """Pass 2 fallback fires when Pass 1 returns non-JSON content."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()
    messages = [{"role": "user", "content": "Generate 1 draft."}]

    bad_response = {
        "choices": [{"message": {"content": "Sorry, I cannot do that."}}]
    }
    good_response = {
        "choices": [
            {"message": {"content": "```json\n" + json.dumps(VALID_SCHEMA_RESPONSE) + "\n```"}}
        ]
    }
    with patch("requests.post", side_effect=[_mock_response(bad_response), _mock_response(good_response)]):
        result = client.generate_agent_drafts(
            model_config=cfg,
            api_key="sk-test",
            messages=messages,
            n=1,
            temperature=0.7,
            top_p=1.0,
            output_requirements=None,
            reference_image_urls=[],
        )
    assert result["drafts"][0]["title"] == "低卡早餐推荐"


def test_generate_agent_drafts_pass2_strips_fences():
    """Markdown fences are stripped before JSON parsing in fallback."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()
    messages = [{"role": "user", "content": "Generate 1 draft."}]

    fenced = "```json\n" + json.dumps(VALID_SCHEMA_RESPONSE) + "\n```"
    bad_p1 = {"choices": [{"message": {"content": "not json"}}]}
    good_p2 = {"choices": [{"message": {"content": fenced}}]}
    with patch("requests.post", side_effect=[_mock_response(bad_p1), _mock_response(good_p2)]):
        result = client.generate_agent_drafts(
            model_config=cfg,
            api_key="sk-test",
            messages=messages,
            n=1,
            temperature=0.7,
            top_p=1.0,
            output_requirements=None,
            reference_image_urls=[],
        )
    assert "drafts" in result


def test_generate_agent_drafts_raises_when_both_passes_fail():
    """ValueError raised when both passes return non-JSON."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()
    messages = [{"role": "user", "content": "Generate 1 draft."}]

    bad = {"choices": [{"message": {"content": "not json at all"}}]}
    with patch("requests.post", side_effect=[_mock_response(bad), _mock_response(bad)]):
        with pytest.raises(ValueError, match="structured output"):
            client.generate_agent_drafts(
                model_config=cfg,
                api_key="sk-test",
                messages=messages,
                n=1,
                temperature=0.7,
                top_p=1.0,
                output_requirements=None,
                reference_image_urls=[],
            )


def test_serialize_draft_includes_tags():
    """_serialize_draft must include tags in its output dict."""
    from backend.app.api.ai import _serialize_draft
    from backend.app.models import AiDraft
    from datetime import datetime

    draft = AiDraft()
    draft.id = 1
    draft.platform = "xhs"
    draft.title = "Test"
    draft.body = "Body"
    draft.tags = [{"name": "低卡早餐"}]
    draft.source_note_id = None
    draft.created_at = datetime(2026, 5, 12, 9, 0, 0)

    result = _serialize_draft(draft)
    assert "tags" in result
    assert result["tags"] == [{"name": "低卡早餐"}]


# ---------------------------------------------------------------------------
# Integration tests for POST /api/ai/agent-drafts/chat/completions
# ---------------------------------------------------------------------------

import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import app
from backend.app.core.database import get_db, Base
from backend.app.core.deps import get_current_user
from backend.app.core.security import encrypt_text
from backend.app.models import User, ModelConfig
from backend.app.api.ai import get_text_ai_client, get_image_ai_client


def _make_test_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _seed_user_and_models(session, with_image_model=True):
    user = User(username="tester", email="tester@test.com", password_hash="x")
    session.add(user)
    session.flush()

    text_model = ModelConfig(
        user_id=user.id,
        name="test-text",
        model_type="text",
        provider="openai",
        model_name="gpt-test",
        base_url="http://fake-llm",
        encrypted_api_key=encrypt_text("sk-test"),
        is_default=True,
    )
    session.add(text_model)

    if with_image_model:
        image_model = ModelConfig(
            user_id=user.id,
            name="test-image",
            model_type="image",
            provider="openai",
            model_name="dall-e-test",
            base_url="http://fake-image-llm",
            encrypted_api_key=encrypt_text("sk-img-test"),
            is_default=True,
        )
        session.add(image_model)

    session.commit()
    session.refresh(user)
    return user


def _override_app(tmp_path, *, with_image_model=True, text_client, image_client=None):
    engine, SessionLocal = _make_test_db(tmp_path)
    db = SessionLocal()
    user = _seed_user_and_models(db, with_image_model=with_image_model)
    db.close()

    def override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_text_ai_client] = lambda: text_client
    if image_client is not None:
        app.dependency_overrides[get_image_ai_client] = lambda: image_client
    return engine, SessionLocal


def _cleanup(engine, SessionLocal):
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_text_ai_client, None)
    app.dependency_overrides.pop(get_image_ai_client, None)
    SessionLocal.close_all()
    engine.dispose()


_VALID_REQUEST = {
    "messages": [{"role": "user", "content": "Generate 1 low-calorie breakfast draft."}],
    "n": 1,
    "metadata": {"platform": "xhs"},
    "image_options": {"n": 0},
}

_TEXT_CLIENT_RESPONSE = {
    "drafts": [
        {
            "title": "低卡早餐推荐",
            "body": "这款早餐热量低，口感好。",
            "tags": ["低卡早餐", "健康饮食"],
            "image_prompt": {
                "positive_prompt": "healthy breakfast",
                "negative_prompt": "junk food",
                "reference_strategy": "no_reference",
            },
        }
    ]
}


def test_agent_drafts_requires_auth():
    client = TestClient(app)
    response = client.post("/api/ai/agent-drafts/chat/completions", json=_VALID_REQUEST)
    assert response.status_code == 401


def test_agent_drafts_missing_text_model(tmp_path):
    engine, SessionLocal = _make_test_db(tmp_path)
    db = SessionLocal()
    user = User(username="u2", email="u2@test.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    def override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json=_VALID_REQUEST)
        assert response.status_code == 400
        assert "text model" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        SessionLocal.close_all()
        engine.dispose()


def test_agent_drafts_creates_drafts_with_tags(tmp_path):
    text_client = MagicMock()
    text_client.generate_agent_drafts.return_value = _TEXT_CLIENT_RESPONSE
    engine, SessionLocal = _override_app(tmp_path, with_image_model=False, text_client=text_client)
    try:
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json=_VALID_REQUEST)
        assert response.status_code == 200
        body = response.json()
        content = __import__("json").loads(body["choices"][0]["message"]["content"])
        assert content["created_count"] == 1
        assert content["failed_count"] == 0
        draft_tags = content["items"][0]["draft"]["tags"]
        assert draft_tags == [{"name": "低卡早餐"}, {"name": "健康饮食"}]
    finally:
        _cleanup(engine, SessionLocal)


def test_agent_drafts_image_failure_keeps_draft(tmp_path):
    text_client = MagicMock()
    text_client.generate_agent_drafts.return_value = _TEXT_CLIENT_RESPONSE

    image_client = MagicMock()
    image_client.generate_image.side_effect = Exception("upstream timeout")

    engine, SessionLocal = _override_app(
        tmp_path, with_image_model=True, text_client=text_client, image_client=image_client
    )
    try:
        request = {**_VALID_REQUEST, "image_options": {"n": 1}}
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json=request)
        assert response.status_code == 200
        body = response.json()
        content = __import__("json").loads(body["choices"][0]["message"]["content"])
        assert content["created_count"] == 1
        item = content["items"][0]
        assert item["status"] == "partial"
        assert len(item["errors"]) > 0
        assert item["draft"]["id"] is not None
    finally:
        _cleanup(engine, SessionLocal)


def test_agent_drafts_missing_image_model_when_images_requested(tmp_path):
    text_client = MagicMock()
    text_client.generate_agent_drafts.return_value = _TEXT_CLIENT_RESPONSE

    engine, SessionLocal = _override_app(tmp_path, with_image_model=False, text_client=text_client)
    try:
        request = {**_VALID_REQUEST, "image_options": {"n": 1}}
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json=request)
        assert response.status_code == 400
        assert "image model" in response.json()["detail"].lower()
    finally:
        _cleanup(engine, SessionLocal)


def test_agent_drafts_full_batch_passes_image_options_to_image_client(tmp_path):
    text_client = MagicMock()
    text_client.generate_agent_drafts.return_value = _TEXT_CLIENT_RESPONSE

    image_client = MagicMock()
    image_client.generate_image.return_value = {"url": "data:image/png;base64,abc"}

    engine, SessionLocal = _override_app(
        tmp_path, with_image_model=True, text_client=text_client, image_client=image_client
    )
    try:
        request = {
            **_VALID_REQUEST,
            "image_options": {
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
                "style": "natural",
                "response_format": "b64_json",
            },
        }
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json=request)
        assert response.status_code == 200
        image_client.generate_image.assert_called_once()
        call_kwargs = image_client.generate_image.call_args.kwargs
        assert call_kwargs["size"] == "1792x1024"
        assert call_kwargs["quality"] == "hd"
        assert call_kwargs["style"] == "natural"
        assert call_kwargs["response_format"] == "b64_json"
    finally:
        _cleanup(engine, SessionLocal)


# ---------------------------------------------------------------------------
# Tests for enhanced draft titles (step=titles returns topics)
# ---------------------------------------------------------------------------

def test_generate_draft_titles_returns_topics():
    """generate_draft_titles returns topics and recommended_topic fields."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()
    messages = [{"role": "user", "content": "Generate breakfast drafts."}]

    api_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "titles": ["标题1", "标题2", "标题3"],
                    "topics": ["低卡早餐", "健康饮食", "减脂餐"],
                })
            }
        }]
    }
    with patch("requests.post", return_value=_mock_response(api_response)):
        result = client.generate_draft_titles(
            model_config=cfg,
            api_key="sk-test",
            messages=messages,
            n=3,
            temperature=0.7,
            top_p=1.0,
        )
    assert "titles" in result
    assert "topics" in result
    assert "recommended_title" in result
    assert "recommended_topic" in result
    assert result["titles"] == ["标题1", "标题2", "标题3"]
    assert result["topics"] == ["低卡早餐", "健康饮食", "减脂餐"]
    assert result["recommended_title"] == "标题1"
    assert result["recommended_topic"] == "低卡早餐"


def test_generate_single_draft_returns_12_layers():
    """generate_single_draft returns cover_strategy, image_prompt_spec, and publish_tips."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()
    messages = [{"role": "user", "content": "Generate a breakfast draft."}]

    api_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "body": "早餐内容正文",
                    "tags": ["早餐", "健康"],
                    "cover_strategy": {
                        "cover_goal": "吸引点击",
                        "cover_type": "食物特写",
                        "visual_core": "色彩鲜艳",
                        "title_space": "上方30%",
                        "text_in_image": False,
                    },
                    "image_prompt_spec": {
                        "L1_publish_goal": "种草低卡早餐",
                        "L2_topic": "低卡早餐",
                        "L3_audience": "减肥人群",
                        "L4_main_subject": "早餐碗",
                        "L5_scene": "厨房台面",
                        "L6_composition": "居中构图",
                        "L7_style": "自然清新",
                        "L8_color_lighting": "自然光",
                        "L9_emotion": "治愈",
                        "L10_details": "健康食材",
                        "L11_platform_adaptation": "小红书封面",
                        "L12_negative_constraints": "不要文字",
                    },
                    "publish_tips": "发布时间建议早上8点",
                })
            }
        }]
    }
    with patch("requests.post", return_value=_mock_response(api_response)):
        result = client.generate_single_draft(
            model_config=cfg,
            api_key="sk-test",
            messages=messages,
            title="低卡早餐",
            temperature=0.7,
            top_p=1.0,
            output_requirements=None,
        )
    assert result["body"] == "早餐内容正文"
    assert "cover_strategy" in result
    assert result["cover_strategy"]["cover_type"] == "食物特写"
    assert "image_prompt_spec" in result
    assert result["image_prompt_spec"]["L1_publish_goal"] == "种草低卡早餐"
    assert "publish_tips" in result


# ---------------------------------------------------------------------------
# Tests for iterate_image_prompt self-iteration
# ---------------------------------------------------------------------------

def test_iterate_image_prompt_converges_in_3_rounds():
    """Prompt iteration converges within max_iterations rounds."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()

    def score_response(score: float, need_rewrite: bool):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "scores": {
                            "theme_clarity": 5, "subject_clarity": 5,
                            "composition_control": 5, "xiaohongshu_fit": 5,
                            "style_consistency": 5, "negative_constraints": 5,
                            "text_risk": 5,
                        },
                        "overall_score": score,
                        "failed_items": [],
                        "improvement_suggestions": [],
                        "whether_need_rewrite": need_rewrite,
                    })
                }
            }]
        }

    call_count = [0]
    def mock_post(request, **kwargs):
        call_count[0] += 1
        url = request if isinstance(request, str) else request.url
        if "chat/completions" in str(url):
            body = request.json() if hasattr(request, "json") else {}
            msgs = body.get("messages", [])
            content = next((m["content"] for m in msgs if isinstance(m.get("content"), str) and "待质检" in m.get("content", "")), None)
            if content:
                return _mock_response(score_response(4.6, False))
            return _mock_response({
                "choices": [{"message": {"content": "a cozy healthy breakfast bowl, natural lighting, top view"}}]
            })
        return _mock_response({})

    with patch("requests.post", side_effect=mock_post):
        result = client.iterate_image_prompt(
            model_config=cfg,
            api_key="sk-test",
            image_prompt_spec={
                "L1_publish_goal": "种草",
                "L2_topic": "早餐",
                "L3_audience": "减肥",
                "L4_main_subject": "碗",
                "L5_scene": "厨房",
                "L6_composition": "居中",
                "L7_style": "清新",
                "L8_color_lighting": "自然光",
                "L9_emotion": "治愈",
                "L10_details": "健康",
                "L11_platform_adaptation": "小红书封面",
                "L12_negative_constraints": "不要文字",
            },
            cover_strategy={"cover_goal": "吸引", "cover_type": "特写", "visual_core": "色彩", "title_space": "上方", "text_in_image": False},
            draft_body="早餐很重要",
            reference_image_urls=[],
            max_iterations=3,
            target_score=4.5,
        )

    assert "final_image_prompt" in result
    assert "iteration_history" in result
    assert result["total_rounds"] >= 1


def test_iterate_image_prompt_respects_max_iterations():
    """Iteration stops after max_iterations even if score is below target."""
    client = OpenAICompatibleTextClient()
    cfg = _make_model_config()

    def mock_post(request, **kwargs):
        url = request if isinstance(request, str) else getattr(request, "url", "")
        body = request.json() if hasattr(request, "json") else {}
        msgs = body.get("messages", [])
        content = next((m.get("content", "") for m in msgs if "待质检" in str(m.get("content", ""))), None)
        if content:
            return _mock_response({
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "scores": {"theme_clarity": 2, "subject_clarity": 2, "composition_control": 2,
                                        "xiaohongshu_fit": 2, "style_consistency": 2, "negative_constraints": 2, "text_risk": 3},
                            "overall_score": 2.5,
                            "failed_items": ["构图不清", "主题模糊"],
                            "improvement_suggestions": ["明确构图", "聚焦主题"],
                            "whether_need_rewrite": True,
                        })
                    }
                }]
            })
        prompt_content = next((m.get("content", "") for m in msgs if isinstance(m.get("content"), str) and "生图提示词" in str(m.get("content", ""))), None)
        if prompt_content:
            return _mock_response({
                "choices": [{"message": {"content": "breakfast bowl photo"}}]
            })
        rewrite_content = next((m.get("content", "") for m in msgs if isinstance(m.get("content"), str) and "原始提示词" in str(m.get("content", ""))), None)
        if rewrite_content:
            return _mock_response({
                "choices": [{"message": {"content": "improved breakfast bowl photo, centered, natural light"}}]
            })
        return _mock_response({"choices": [{"message": {"content": "prompt"}}]})

    with patch("requests.post", side_effect=mock_post):
        result = client.iterate_image_prompt(
            model_config=cfg,
            api_key="sk-test",
            image_prompt_spec={
                "L1_publish_goal": "", "L2_topic": "", "L3_audience": "",
                "L4_main_subject": "", "L5_scene": "", "L6_composition": "",
                "L7_style": "", "L8_color_lighting": "", "L9_emotion": "",
                "L10_details": "", "L11_platform_adaptation": "", "L12_negative_constraints": "",
            },
            cover_strategy={"cover_goal": "", "cover_type": "", "visual_core": "", "title_space": "", "text_in_image": False},
            draft_body="",
            reference_image_urls=[],
            max_iterations=3,
            target_score=4.5,
        )

    # Should stop at max 3 rounds
    assert result["total_rounds"] <= 3
    assert len(result["iteration_history"]) <= 3


def test_iterate_image_prompt_fallback_without_model_config():
    """iterate_image_prompt returns fallback prompt when model config is incomplete."""
    client = OpenAICompatibleTextClient()
    cfg = ModelConfig()
    cfg.base_url = ""
    cfg.model_name = ""

    result = client.iterate_image_prompt(
        model_config=cfg,
        api_key="",
        image_prompt_spec={
            "L1_publish_goal": "种草",
            "L2_topic": "早餐",
            "L3_audience": "减肥",
            "L4_main_subject": "碗",
            "L5_scene": "厨房",
            "L6_composition": "居中",
            "L7_style": "清新",
            "L8_color_lighting": "自然光",
            "L9_emotion": "治愈",
            "L10_details": "健康",
            "L11_platform_adaptation": "小红书封面",
            "L12_negative_constraints": "不要文字",
        },
        cover_strategy={},
        draft_body="早餐内容",
        reference_image_urls=[],
        max_iterations=3,
        target_score=4.5,
    )

    assert "final_image_prompt" in result
    assert result["total_rounds"] == 0
    assert result["iteration_history"] == []


# ---------------------------------------------------------------------------
# Tests for _check_generated_image_quality
# ---------------------------------------------------------------------------

def test_check_generated_image_quality_returns_structured_result():
    """_check_generated_image_quality returns ImageQualityCheck structure."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()

    quality_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_relevant_to_topic": True,
                    "has_text_or_garbled_text": False,
                    "has_logo_or_watermark": False,
                    "has_qrcode": False,
                    "has_sensitive_content": False,
                    "has_deformed_face_or_hands": False,
                    "is_xiaohongshu_cover_ready": True,
                    "has_title_space": True,
                    "need_retry": False,
                    "retry_reason": "",
                })
            }
        }]
    }

    cfg = _make_model_config()
    with patch("requests.post", return_value=_mock_response(quality_response)):
        result = client._check_generated_image_quality(
            image_url="https://example.com/img.png",
            topic="低卡早餐",
            text_model_config=cfg,
            text_api_key="sk-test",
        )

    assert result["need_retry"] is False
    assert result["has_text_or_garbled_text"] is False
    assert result["is_xiaohongshu_cover_ready"] is True


def test_check_generated_image_quality_skips_when_model_lacks_vision_capability():
    """A configured text model without vision capability must not call the vision request."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()
    cfg = _make_model_config(capabilities=["text_generation"])

    with patch("requests.post") as post_mock:
        result = client._check_generated_image_quality(
            image_url="https://example.com/img.png",
            topic="奶油风客厅",
            text_model_config=cfg,
            text_api_key="sk-test",
        )

    assert result["need_retry"] is False
    assert result["vision_check_status"] == "skipped"
    assert "vision" in result["vision_check_message"]
    post_mock.assert_not_called()


def test_check_generated_image_quality_marks_unchecked_when_vision_model_unavailable():
    """Missing text/vision config should be visible instead of silently looking passed."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()
    cfg = _make_model_config(base_url="", model_name="", capabilities=["text_generation", "vision"])

    result = client._check_generated_image_quality(
        image_url="https://example.com/img.png",
        topic="奶油风客厅",
        text_model_config=cfg,
        text_api_key="",
    )

    assert result["need_retry"] is False
    assert result["vision_check_status"] == "skipped"
    assert "未执行视觉质检" in result["vision_check_message"]
    assert "未执行视觉质检" in result["retry_reason"]


def test_check_generated_image_quality_marks_failed_when_vision_call_errors():
    """Vision API errors should be explicit in the returned quality metadata."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()
    cfg = _make_model_config(base_url="http://fake-llm", model_name="gpt-vision", capabilities=["text_generation", "vision"])

    with patch("requests.post", side_effect=RuntimeError("vision model does not support image_url")):
        result = client._check_generated_image_quality(
            image_url="https://example.com/img.png",
            topic="奶油风客厅",
            text_model_config=cfg,
            text_api_key="sk-test",
        )

    assert result["need_retry"] is False
    assert result["vision_check_status"] == "failed"
    assert "未完成视觉质检" in result["vision_check_message"]
    assert "vision model does not support image_url" in result["retry_reason"]


# ---------------------------------------------------------------------------
# Tests for generate_image_with_retry
# ---------------------------------------------------------------------------

def test_generate_image_with_retry_skips_retry_when_pass():
    """Image quality check pass → no retry, url returned directly."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()

    img_cfg = _make_model_config(base_url="http://fake-img", model_name="dall-e")
    txt_cfg = _make_model_config(base_url="http://fake-llm", model_name="gpt-vision", capabilities=["text_generation", "vision"])

    quality_pass = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_relevant_to_topic": True,
                    "has_text_or_garbled_text": False,
                    "has_logo_or_watermark": False,
                    "has_qrcode": False,
                    "has_sensitive_content": False,
                    "has_deformed_face_or_hands": False,
                    "is_xiaohongshu_cover_ready": True,
                    "has_title_space": True,
                    "need_retry": False,
                    "retry_reason": "",
                })
            }
        }]
    }

    img_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "data": [{"url": "https://cdn.example.com/breakfast.png"}]
                })
            }
        }]
    }

    call_count = [0]
    def mock_post(request, **kwargs):
        call_count[0] += 1
        url = str(getattr(request, "url", request)) if hasattr(request, "url") else str(request)
        if "images/generations" in url:
            return _mock_response({"data": [{"url": "https://cdn.example.com/breakfast.png"}]})
        return _mock_response(quality_pass)

    with patch("requests.post", side_effect=mock_post):
        result = client.generate_image_with_retry(
            prompt="healthy breakfast bowl",
            reference_images=None,
            image_model_config=img_cfg,
            image_api_key="sk-img",
            text_model_config=txt_cfg,
            text_api_key="sk-txt",
            topic="低卡早餐",
            max_retries=2,
        )

    assert result["url"] == "https://cdn.example.com/breakfast.png"
    assert result["quality_check"]["need_retry"] is False
    assert len(result["iteration_history"]) == 1


def test_generate_image_with_retry_retries_on_failure():
    """Image quality check fail → retry, correction applied."""
    from backend.app.services.ai_service import OpenAICompatibleImageClient
    client = OpenAICompatibleImageClient()

    img_cfg = _make_model_config(base_url="http://fake-img", model_name="dall-e")
    txt_cfg = _make_model_config(base_url="http://fake-llm", model_name="gpt-vision", capabilities=["text_generation", "vision"])

    quality_fail = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_relevant_to_topic": True,
                    "has_text_or_garbled_text": True,
                    "has_logo_or_watermark": False,
                    "has_qrcode": False,
                    "has_sensitive_content": False,
                    "has_deformed_face_or_hands": False,
                    "is_xiaohongshu_cover_ready": False,
                    "has_title_space": False,
                    "need_retry": True,
                    "retry_reason": "has_text_or_garbled_text",
                })
            }
        }]
    }
    quality_pass = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_relevant_to_topic": True,
                    "has_text_or_garbled_text": False,
                    "has_logo_or_watermark": False,
                    "has_qrcode": False,
                    "has_sensitive_content": False,
                    "has_deformed_face_or_hands": False,
                    "is_xiaohongshu_cover_ready": True,
                    "has_title_space": True,
                    "need_retry": False,
                    "retry_reason": "",
                })
            }
        }]
    }

    call_count = [0]
    def mock_post(request, **kwargs):
        call_count[0] += 1
        url = str(getattr(request, "url", request)) if hasattr(request, "url") else str(request)
        if "images/generations" in url:
            return _mock_response({"data": [{"url": f"https://cdn.example.com/img_{call_count[0]}.png"}]})
        return _mock_response(quality_pass if call_count[0] > 2 else quality_fail)

    with patch("requests.post", side_effect=mock_post):
        result = client.generate_image_with_retry(
            prompt="healthy breakfast bowl",
            reference_images=None,
            image_model_config=img_cfg,
            image_api_key="sk-img",
            text_model_config=txt_cfg,
            text_api_key="sk-txt",
            topic="低卡早餐",
            max_retries=2,
        )

    assert result["url"] != ""
    assert len(result["iteration_history"]) >= 1


# ---------------------------------------------------------------------------
# API-level tests for step-mode enhancements
# ---------------------------------------------------------------------------

def test_step_titles_returns_topics(tmp_path):
    """step=titles API response includes topics and recommended_topic."""
    text_client = MagicMock()
    text_client.generate_draft_titles.return_value = {
        "titles": ["标题1", "标题2"],
        "recommended_title": "标题1",
        "topics": ["主题A", "主题B"],
        "recommended_topic": "主题A",
    }
    engine, SessionLocal = _override_app(
        tmp_path, with_image_model=False, text_client=text_client
    )
    try:
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json={
            "messages": [{"role": "user", "content": "generate"}],
            "n": 2,
            "step": "titles",
            "metadata": {"platform": "xhs"},
            "image_options": {"n": 0},
        })
        assert response.status_code == 200
        content = json.loads(response.json()["choices"][0]["message"]["content"])
        assert "topics" in content
        assert "recommended_topic" in content
        assert content["topics"] == ["主题A", "主题B"]
        assert content["recommended_topic"] == "主题A"
    finally:
        _cleanup(engine, SessionLocal)


def test_step_draft_returns_cover_strategy_and_publish_tips(tmp_path):
    """step=draft API response includes cover_strategy, image_prompt_spec, publish_tips."""
    text_client = MagicMock()
    text_client.generate_single_draft.return_value = {
        "title": "测试标题",
        "body": "正文内容",
        "tags": ["标签1"],
        "cover_strategy": {"cover_goal": "吸引点击", "cover_type": "特写", "visual_core": "色彩", "title_space": "上方", "text_in_image": False},
        "image_prompt_spec": {"L1_publish_goal": "种草", "L2_topic": "测试", "L3_audience": "", "L4_main_subject": "", "L5_scene": "", "L6_composition": "", "L7_style": "", "L8_color_lighting": "", "L9_emotion": "", "L10_details": "", "L11_platform_adaptation": "", "L12_negative_constraints": ""},
        "publish_tips": "建议早上9点发布",
    }
    engine, SessionLocal = _override_app(
        tmp_path, with_image_model=False, text_client=text_client
    )
    try:
        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json={
            "messages": [{"role": "user", "content": "generate"}],
            "step": "draft",
            "selected_title": "测试标题",
            "metadata": {"platform": "xhs"},
            "image_options": {"n": 0},
        })
        assert response.status_code == 200
        content = json.loads(response.json()["choices"][0]["message"]["content"])
        assert "cover_strategy" in content
        assert "image_prompt_spec" in content
        assert "publish_tips" in content
        assert content["cover_strategy"]["cover_type"] == "特写"
    finally:
        _cleanup(engine, SessionLocal)


def test_step_images_returns_final_prompt_and_passes_image_options(tmp_path):
    """step=images returns final_image_prompt and forwards image options into retry generation."""
    text_client = MagicMock()
    text_client.iterate_image_prompt.return_value = {
        "final_image_prompt": "final cozy living room prompt",
        "iteration_history": [],
        "total_rounds": 1,
    }
    image_client = MagicMock()
    image_client.generate_image_with_retry.return_value = {
        "url": "data:image/png;base64,abc",
        "iteration_history": [],
        "quality_check": {"need_retry": False},
        "final_image_prompt": "final cozy living room prompt",
    }

    engine, SessionLocal = _override_app(
        tmp_path, with_image_model=True, text_client=text_client, image_client=image_client
    )
    try:
        db = SessionLocal()
        user = db.query(User).first()
        from backend.app.models import AiDraft

        draft = AiDraft(user_id=user.id, platform="xhs", title="奶油风客厅", body="正文")
        db.add(draft)
        db.commit()
        db.refresh(draft)
        db.close()

        client = TestClient(app)
        response = client.post("/api/ai/agent-drafts/chat/completions", json={
            "messages": [{"role": "user", "content": "generate images"}],
            "step": "images",
            "draft_id": draft.id,
            "cover_strategy": {"cover_goal": "吸引点击"},
            "image_prompt_spec": {"L1_publish_goal": "室内设计"},
            "draft_body": "正文",
            "metadata": {"platform": "xhs"},
            "image_options": {
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
                "style": "natural",
                "response_format": "b64_json",
            },
        })
        assert response.status_code == 200
        content = json.loads(response.json()["choices"][0]["message"]["content"])
        assert content["final_image_prompt"] == "final cozy living room prompt"
        image_client.generate_image_with_retry.assert_called_once()
        call_kwargs = image_client.generate_image_with_retry.call_args.kwargs
        assert call_kwargs["size"] == "1792x1024"
        assert call_kwargs["quality"] == "hd"
        assert call_kwargs["style"] == "natural"
        assert call_kwargs["response_format"] == "b64_json"
    finally:
        _cleanup(engine, SessionLocal)

