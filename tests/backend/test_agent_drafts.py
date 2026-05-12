import json
import pytest
from unittest.mock import MagicMock, patch
from backend.app.services.ai_service import OpenAICompatibleTextClient
from backend.app.models import ModelConfig


def _make_model_config(base_url="http://fake-llm", model_name="gpt-test"):
    cfg = ModelConfig()
    cfg.base_url = base_url
    cfg.model_name = model_name
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
    cfg = _make_model_config()
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
