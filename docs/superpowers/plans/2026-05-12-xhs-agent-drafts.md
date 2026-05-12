# XHS Agent Drafts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conversational XHS draft generation page that calls a new backend orchestration endpoint to produce multiple Xiaohongshu drafts and AI-generated images in a single run.

**Architecture:** A new `POST /api/ai/agent-drafts/chat/completions` endpoint in the existing FastAPI AI router orchestrates text generation (via the default text model), draft creation, and image generation (via the default image model). A new React page at `/platforms/xhs/agent-drafts` lets the user describe requirements, then shows per-draft result cards. The backend uses the existing `_recorded_text_task` task-tracking pattern and the existing `AiDraft`, `AiGeneratedAsset`, and `DraftAsset` models—no migration needed.

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy + Pydantic v2; React 18 + TypeScript + Ant Design; OpenAI-compatible chat completions API; existing `OpenAICompatibleTextClient` and `OpenAICompatibleImageClient`; pytest + FastAPI TestClient.

---

## File Map

**Create:**
- `frontend/src/pages/platforms/xhs/agent-drafts-page.tsx` — new XHS Agent Drafts page component
- `tests/backend/test_agent_drafts.py` — all backend tests for the new endpoint

**Modify:**
- `backend/app/services/ai_service.py` — extend `TextAiClient` Protocol + implement `generate_agent_drafts` on `OpenAICompatibleTextClient`
- `backend/app/api/ai.py` — add request/response models, import `DraftAsset`, update `_serialize_draft`, add new endpoint handler
- `frontend/src/types/index.ts` — add 4 new TypeScript interfaces
- `frontend/src/lib/api.ts` — add `generateAgentDrafts()` API client function
- `frontend/src/app/router.tsx` — register `/platforms/xhs/agent-drafts` route
- `frontend/src/components/layout/app-shell.tsx` — add sidebar nav entry

---

## Task 1: Extend TextAiClient Protocol and implement generate_agent_drafts

**Files:**
- Modify: `backend/app/services/ai_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_agent_drafts.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

```
python -m pytest tests/backend/test_agent_drafts.py -v
```

Expected: 4 errors — `OpenAICompatibleTextClient` has no method `generate_agent_drafts`.

- [ ] **Step 3: Add generate_agent_drafts to TextAiClient Protocol**

In `backend/app/services/ai_service.py`, inside the `TextAiClient` Protocol class (after the existing `polish_text` method), add:

```python
    def generate_agent_drafts(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        reference_image_urls: list[str],
    ) -> dict:
        ...
```

- [ ] **Step 4: Implement generate_agent_drafts on OpenAICompatibleTextClient**

Add this method to `OpenAICompatibleTextClient` (after `polish_text`):

```python
    _AGENT_DRAFT_SCHEMA = {
        "type": "object",
        "properties": {
            "drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "image_prompt": {
                            "type": "object",
                            "properties": {
                                "positive_prompt": {"type": "string"},
                                "negative_prompt": {"type": "string"},
                                "reference_strategy": {"type": "string"},
                            },
                            "required": ["positive_prompt", "negative_prompt", "reference_strategy"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["title", "body", "tags", "image_prompt"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["drafts"],
        "additionalProperties": False,
    }

    @staticmethod
    def _strip_fences(text: str) -> str:
        import re
        return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", text.strip()))

    @staticmethod
    def _validate_agent_draft_schema(data: dict) -> None:
        if "drafts" not in data or not isinstance(data["drafts"], list):
            raise ValueError("structured output missing 'drafts' array")
        for item in data["drafts"]:
            for key in ("title", "body", "tags", "image_prompt"):
                if key not in item:
                    raise ValueError(f"structured output item missing '{key}'")

    def _call_chat(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        temperature: float,
        top_p: float,
        extra_body: dict | None = None,
    ) -> str:
        if not model_config.base_url:
            raise ValueError("Text model base_url is required")
        if not model_config.model_name:
            raise ValueError("Text model_name is required")
        if not api_key:
            raise ValueError("Text model api_key is required")

        body: dict = {
            "model": model_config.model_name,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        if extra_body:
            body.update(extra_body)

        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc

    def generate_agent_drafts(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        reference_image_urls: list[str],
    ) -> dict:
        import json

        prepared = list(messages)
        if output_requirements:
            # inject into existing system message or prepend one
            for msg in prepared:
                if msg.get("role") == "system":
                    msg = dict(msg)
                    msg["content"] = f"{msg['content']}\n\nOutput requirements: {output_requirements}"
                    prepared[prepared.index(msg)] = msg
                    break
            else:
                prepared.insert(0, {"role": "system", "content": f"Output requirements: {output_requirements}"})

        schema_body = {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "xhs_agent_draft_batch",
                    "strict": True,
                    "schema": self._AGENT_DRAFT_SCHEMA,
                },
            }
        }

        # Pass 1: native structured output
        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=prepared,
                temperature=temperature,
                top_p=top_p,
                extra_body=schema_body,
            )
            data = json.loads(content)
            self._validate_agent_draft_schema(data)
            return data
        except Exception:
            pass

        # Pass 2: prompt injection fallback
        import json as _json
        schema_str = _json.dumps(self._AGENT_DRAFT_SCHEMA, ensure_ascii=False)
        injection = (
            "\n\nYou must respond with a single valid JSON object and nothing else.\n"
            "Do not wrap the JSON in markdown code fences.\n"
            f"The JSON must conform to this schema:\n<schema>\n{schema_str}\n</schema>"
        )
        fallback_messages = list(prepared)
        injected = False
        for i, msg in enumerate(fallback_messages):
            if msg.get("role") == "system":
                fallback_messages[i] = dict(msg)
                fallback_messages[i]["content"] = str(msg["content"]) + injection
                injected = True
                break
        if not injected:
            fallback_messages.insert(0, {"role": "system", "content": injection.strip()})

        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=fallback_messages,
                temperature=temperature,
                top_p=top_p,
            )
            stripped = self._strip_fences(content)
            data = json.loads(stripped)
            self._validate_agent_draft_schema(data)
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"structured output failed after both passes: {exc}") from exc
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/backend/test_agent_drafts.py::test_generate_agent_drafts_pass1_success tests/backend/test_agent_drafts.py::test_generate_agent_drafts_pass2_fallback_on_bad_json tests/backend/test_agent_drafts.py::test_generate_agent_drafts_pass2_strips_fences tests/backend/test_agent_drafts.py::test_generate_agent_drafts_raises_when_both_passes_fail -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_service.py tests/backend/test_agent_drafts.py
git commit -m "feat: add generate_agent_drafts to TextAiClient with two-pass fallback"
```

---

## Task 2: Backend models and _serialize_draft update

**Files:**
- Modify: `backend/app/api/ai.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_agent_drafts.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

```
python -m pytest tests/backend/test_agent_drafts.py::test_serialize_draft_includes_tags -v
```

Expected: FAILED — `tags` key not in result.

- [ ] **Step 3: Update _serialize_draft to include tags**

In `backend/app/api/ai.py`, replace `_serialize_draft` (lines 76-84):

```python
def _serialize_draft(draft: AiDraft) -> dict:
    return {
        "id": draft.id,
        "platform": draft.platform,
        "title": draft.title,
        "body": draft.body,
        "tags": draft.tags or [],
        "source_note_id": draft.source_note_id,
        "created_at": draft.created_at.isoformat(),
    }
```

- [ ] **Step 4: Add DraftAsset import and new request/response models**

In `backend/app/api/ai.py`, replace the models import line 14:

```python
from backend.app.models import AiDraft, AiGeneratedAsset, DraftAsset, ModelConfig, Task, User
```

Then add these Pydantic models after `DescribeImageRequest` (before `get_text_ai_client`):

```python
class _ImageUrlPart(BaseModel):
    url: str


class _ContentPart(BaseModel):
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: _ImageUrlPart | None = None


class _AgentMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[_ContentPart]


class _ImageOptions(BaseModel):
    model: str | None = None
    n: int = Field(default=1, ge=0, le=3)
    size: str | None = None
    quality: str | None = None
    style: str | None = None
    response_format: str | None = None


class _AgentMetadata(BaseModel):
    platform: Literal["xhs"]
    save_to_drafts: str | None = None
    output_requirements: str | None = None


class AgentDraftsChatRequest(BaseModel):
    model: str | None = None
    messages: list[_AgentMessage] = Field(min_length=1)
    n: int = Field(default=3, ge=1, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stream: Literal[False] | None = None
    response_format: dict[str, Any] | None = None
    metadata: _AgentMetadata | None = None
    image_options: _ImageOptions = Field(default_factory=_ImageOptions)
    user: str | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/backend/test_agent_drafts.py::test_serialize_draft_includes_tags -v
```

Expected: PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ai.py
git commit -m "feat: add agent drafts request models, DraftAsset import, fix _serialize_draft tags"
```

---

## Task 3: Backend orchestration endpoint

**Files:**
- Modify: `backend/app/api/ai.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/backend/test_agent_drafts.py`:

```python
import time
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
    user = User(username="tester", hashed_password="x")
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
            base_url="http://fake-image",
            encrypted_api_key=encrypt_text("sk-img"),
            is_default=True,
        )
        session.add(image_model)

    session.commit()
    session.refresh(user)
    return user


def _override_app(tmp_path, with_image_model=True, text_client=None, image_client=None):
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
        s = SessionLocal()
        u = s.get(User, user.id)
        s.close()
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    if text_client is not None:
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
    user = User(username="u2", hashed_password="x")
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
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/backend/test_agent_drafts.py::test_agent_drafts_requires_auth tests/backend/test_agent_drafts.py::test_agent_drafts_missing_text_model tests/backend/test_agent_drafts.py::test_agent_drafts_creates_drafts_with_tags tests/backend/test_agent_drafts.py::test_agent_drafts_image_failure_keeps_draft tests/backend/test_agent_drafts.py::test_agent_drafts_missing_image_model_when_images_requested -v
```

Expected: all FAILED — endpoint does not exist yet.

- [ ] **Step 3: Implement the orchestration endpoint**

Add this helper and endpoint to `backend/app/api/ai.py` (after the `generate_image` endpoint, before any other existing routes you want to keep organized near the end):

```python
def _extract_message_parts(messages: list[_AgentMessage]) -> tuple[list[dict], list[str]]:
    """Convert Pydantic message models to plain dicts; extract reference image URLs."""
    plain: list[dict] = []
    ref_urls: list[str] = []
    for msg in messages:
        if isinstance(msg.content, str):
            plain.append({"role": msg.role, "content": msg.content})
        else:
            parts: list[dict] = []
            for part in msg.content:
                if part.type == "text":
                    parts.append({"type": "text", "text": part.text or ""})
                elif part.type == "image_url" and part.image_url:
                    parts.append({"type": "image_url", "image_url": {"url": part.image_url.url}})
                    ref_urls.append(part.image_url.url)
            plain.append({"role": msg.role, "content": parts})
    return plain, ref_urls


@router.post("/agent-drafts/chat/completions")
def agent_drafts_chat_completions(
    payload: AgentDraftsChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
):
    import json
    import time

    text_model_config, text_api_key = _text_model_context(db, current_user)

    images_per_draft = payload.image_options.n
    image_model_config = None
    image_api_key = ""
    if images_per_draft > 0:
        image_model_config, image_api_key = _image_model_context(db, current_user)

    plain_messages, ref_urls = _extract_message_parts(payload.messages)
    output_requirements = payload.metadata.output_requirements if payload.metadata else None

    task = Task(
        user_id=current_user.id,
        platform="xhs",
        task_type="ai_agent_drafts_generate",
        status="running",
        progress=10,
        payload={
            "n": payload.n,
            "images_per_draft": images_per_draft,
            "reference_image_count": len(ref_urls),
            "items": [],
        },
    )
    db.add(task)
    db.flush()

    try:
        structured = text_ai_client.generate_agent_drafts(
            model_config=text_model_config,
            api_key=text_api_key,
            messages=plain_messages,
            n=payload.n,
            temperature=payload.temperature,
            top_p=payload.top_p,
            output_requirements=output_requirements,
            reference_image_urls=ref_urls,
        )
    except ValueError as exc:
        task.status = "failed"
        task.progress = 100
        task.payload = {**(task.payload or {}), "error": str(exc)}
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        task.status = "failed"
        task.progress = 100
        task.payload = {**(task.payload or {}), "error": str(exc)}
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI text generation failed: {exc}") from exc

    result_items: list[dict] = []
    task_items: list[dict] = []
    created_count = 0
    failed_count = 0

    for idx, draft_data in enumerate(structured.get("drafts", [])):
        raw_tags: list[str] = draft_data.get("tags") or []
        stored_tags = [{"name": t} for t in raw_tags]
        image_prompt_data: dict = draft_data.get("image_prompt") or {}

        draft = AiDraft(
            user_id=current_user.id,
            platform="xhs",
            title=draft_data.get("title") or "",
            body=draft_data.get("body") or "",
            tags=stored_tags,
        )
        db.add(draft)
        db.flush()
        created_count += 1

        item_assets: list[dict] = []
        item_errors: list[str] = []
        asset_ids: list[int] = []

        if images_per_draft > 0 and image_model_config is not None:
            positive_prompt = image_prompt_data.get("positive_prompt") or draft_data.get("title") or ""
            for img_idx in range(images_per_draft):
                try:
                    img_result = image_ai_client.generate_image(
                        model_config=image_model_config,
                        api_key=image_api_key,
                        prompt=positive_prompt,
                        reference_images=ref_urls if ref_urls else None,
                    )
                    image_url = img_result.get("url") or ""
                    gen_asset = AiGeneratedAsset(
                        user_id=current_user.id,
                        draft_id=draft.id,
                        prompt=positive_prompt,
                        model_name=image_model_config.model_name,
                        params={"size": payload.image_options.size, "style": payload.image_options.style},
                        file_path="",
                    )
                    db.add(gen_asset)
                    db.flush()
                    draft_asset = DraftAsset(
                        draft_id=draft.id,
                        asset_type="image",
                        url=image_url,
                        local_path="",
                        sort_order=img_idx,
                    )
                    db.add(draft_asset)
                    db.flush()
                    asset_ids.append(draft_asset.id)
                    item_assets.append({
                        "id": draft_asset.id,
                        "draft_id": draft.id,
                        "asset_type": "image",
                        "url": image_url,
                        "local_path": "",
                        "sort_order": img_idx,
                    })
                except Exception as exc:
                    item_errors.append(f"Image generation failed: {exc}")

        item_status = "completed" if not item_errors else "partial"
        result_items.append({
            "draft": _serialize_draft(draft),
            "image_prompt": image_prompt_data,
            "assets": item_assets,
            "status": item_status,
            "errors": item_errors,
        })
        task_items.append({
            "index": idx,
            "draft_id": draft.id,
            "status": item_status,
            "asset_ids": asset_ids,
            "errors": item_errors,
        })

    task.status = "completed"
    task.progress = 100
    task.payload = {
        **(task.payload or {}),
        "items": task_items,
        "created_count": created_count,
        "failed_count": failed_count,
    }
    db.commit()

    batch_result = {
        "items": result_items,
        "created_count": created_count,
        "failed_count": failed_count,
    }

    return {
        "id": f"chatcmpl_xhs_agent_drafts_{task.id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.model or "default",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(batch_result, ensure_ascii=False),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/backend/test_agent_drafts.py::test_agent_drafts_requires_auth tests/backend/test_agent_drafts.py::test_agent_drafts_missing_text_model tests/backend/test_agent_drafts.py::test_agent_drafts_creates_drafts_with_tags tests/backend/test_agent_drafts.py::test_agent_drafts_image_failure_keeps_draft tests/backend/test_agent_drafts.py::test_agent_drafts_missing_image_model_when_images_requested -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Run all backend tests to check for regressions**

```
python -m pytest tests/backend/ -v
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ai.py
git commit -m "feat: add POST /api/ai/agent-drafts/chat/completions orchestration endpoint"
```

---

## Task 4: Frontend TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Append the new type definitions**

At the end of `frontend/src/types/index.ts`, add:

```typescript
export interface AgentDraftRequestMessage {
  role: "system" | "user" | "assistant";
  content:
    | string
    | Array<
        | { type: "text"; text: string }
        | { type: "image_url"; image_url: { url: string } }
      >;
}

export interface AgentDraftPayload {
  model?: string;
  messages: AgentDraftRequestMessage[];
  n?: number;
  temperature?: number;
  top_p?: number;
  stream?: false;
  response_format?: {
    type: "json_schema";
    json_schema: {
      name: string;
      strict: boolean;
      schema: Record<string, unknown>;
    };
  };
  metadata?: {
    platform: "xhs";
    save_to_drafts?: string;
    output_requirements?: string;
  };
  image_options?: {
    model?: string;
    n?: number;
    size?: string;
    quality?: string;
    style?: string;
    response_format?: string;
  };
  user?: string;
}

export interface AgentDraftItem {
  draft: {
    id: number;
    platform: string;
    title: string;
    body: string;
    tags: Array<{ name: string }>;
    created_at: string;
  };
  image_prompt: {
    positive_prompt: string;
    negative_prompt: string;
    reference_strategy: string;
  };
  assets: Array<{
    id: number;
    draft_id: number;
    asset_type: string;
    url: string;
    local_path: string;
    sort_order: number;
  }>;
  status: "completed" | "partial" | "failed";
  errors: string[];
}

export interface AgentDraftBatchResult {
  items: AgentDraftItem[];
  created_count: number;
  failed_count: number;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```

Expected: no errors for the new types (existing errors unrelated to this change, if any, are pre-existing).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add AgentDraft TypeScript types"
```

---

## Task 5: Frontend API client function

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Read the end of api.ts to find the right insertion point**

Run: `grep -n "export async function\|export function" frontend/src/lib/api.ts | tail -10`

Find the last exported function so the new one is added in the right place.

- [ ] **Step 2: Add the generateAgentDrafts function**

At the end of `frontend/src/lib/api.ts`, add:

```typescript
export async function generateAgentDrafts(
  payload: AgentDraftPayload
): Promise<AgentDraftBatchResult> {
  const res = await apiClient.post<{
    choices: Array<{ message: { content: string } }>;
  }>("/api/ai/agent-drafts/chat/completions", payload);
  return JSON.parse(res.data.choices[0].message.content) as AgentDraftBatchResult;
}
```

Make sure `AgentDraftPayload` and `AgentDraftBatchResult` are imported from `../types`. Check the existing import line at the top of `api.ts` for the types import and add those two names to it.

- [ ] **Step 3: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add generateAgentDrafts API client function"
```

---

## Task 6: Frontend page component

**Files:**
- Create: `frontend/src/pages/platforms/xhs/agent-drafts-page.tsx`

- [ ] **Step 1: Create the page component**

Create `frontend/src/pages/platforms/xhs/agent-drafts-page.tsx`:

```tsx
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  PictureOutlined,
  RobotOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Form,
  Image,
  Input,
  InputNumber,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import { generateAgentDrafts } from "../../../lib/api";
import type { AgentDraftBatchResult, AgentDraftItem } from "../../../types";

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

function DraftResultCard({ item }: { item: AgentDraftItem }) {
  const statusIcon =
    item.status === "completed" ? (
      <CheckCircleOutlined style={{ color: "#52c41a" }} />
    ) : item.status === "partial" ? (
      <ExclamationCircleOutlined style={{ color: "#faad14" }} />
    ) : (
      <ExclamationCircleOutlined style={{ color: "#ff4d4f" }} />
    );

  return (
    <Card
      size="small"
      title={
        <Space>
          {statusIcon}
          <Text strong style={{ fontSize: 13 }}>
            {item.draft.title || "（无标题）"}
          </Text>
          <Badge
            count={`草稿 #${item.draft.id}`}
            style={{ background: "#1668dc", fontSize: 11 }}
          />
        </Space>
      }
      style={{ marginBottom: 12 }}
    >
      <Paragraph
        ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
        style={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
      >
        {item.draft.body}
      </Paragraph>
      {item.draft.tags.length > 0 && (
        <Space wrap style={{ marginBottom: 8 }}>
          {item.draft.tags.map((t) => (
            <Tag key={t.name} color="blue" style={{ fontSize: 11 }}>
              #{t.name}
            </Tag>
          ))}
        </Space>
      )}
      {item.assets.length > 0 && (
        <Image.PreviewGroup>
          <Space wrap>
            {item.assets.map((a) => (
              <Image
                key={a.id}
                src={a.url}
                width={80}
                height={80}
                style={{ objectFit: "cover", borderRadius: 4 }}
                placeholder={
                  <Spin
                    indicator={<LoadingOutlined />}
                    style={{ lineHeight: "80px" }}
                  />
                }
              />
            ))}
          </Space>
        </Image.PreviewGroup>
      )}
      {item.errors.length > 0 && (
        <Alert
          type="warning"
          style={{ marginTop: 8, fontSize: 11 }}
          message={item.errors.join("; ")}
          showIcon
        />
      )}
    </Card>
  );
}

export function XhsAgentDraftsPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentDraftBatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form] = Form.useForm<{
    request: string;
    n: number;
    images_per_draft: number;
    output_requirements: string;
  }>();

  const handleGenerate = async () => {
    const values = await form.validateFields();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await generateAgentDrafts({
        messages: [
          {
            role: "system",
            content:
              "You are a Xiaohongshu content strategist and visual prompt engineer. Generate publish-ready XHS draft candidates.",
          },
          { role: "user", content: values.request },
        ],
        n: values.n,
        metadata: {
          platform: "xhs",
          output_requirements: values.output_requirements || undefined,
        },
        image_options: { n: values.images_per_draft },
      });
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="XHS · AI"
        title="Agent 草稿生成"
        description="描述内容需求，一次生成多篇可发布的小红书草稿及配套图片。"
      />

      <Row gutter={24}>
        <Col xs={24} lg={10}>
          <Card title="生成设置" size="small" style={{ marginBottom: 16 }}>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ n: 3, images_per_draft: 1, request: "", output_requirements: "" }}
            >
              <Form.Item
                name="request"
                label="内容需求"
                rules={[{ required: true, message: "请描述内容需求" }]}
              >
                <TextArea
                  rows={5}
                  placeholder="例如：生成3篇低卡早餐种草笔记，受众是减脂人群，语气自然亲切，附带图片提示词。"
                  maxLength={2000}
                  showCount
                />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="n" label="草稿数量">
                    <InputNumber min={1} max={10} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="images_per_draft" label="每篇图片数">
                    <InputNumber min={0} max={3} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="output_requirements" label="输出要求（可选）">
                <Input placeholder="例如：每篇必须包含3个标签，突出卖点" maxLength={500} />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  loading={loading}
                  onClick={() => void handleGenerate()}
                  block
                >
                  开始生成
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          {loading && (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <Spin
                indicator={<LoadingOutlined style={{ fontSize: 32 }} />}
                tip="正在生成草稿…"
              />
            </div>
          )}
          {error && (
            <Alert type="error" message="生成失败" description={error} showIcon style={{ marginBottom: 16 }} />
          )}
          {result && !loading && (
            <>
              <Space style={{ marginBottom: 12 }}>
                <RobotOutlined />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  生成完成：{result.created_count} 篇草稿，{result.failed_count} 篇失败
                </Text>
              </Space>
              {result.items.map((item, i) => (
                <DraftResultCard key={item.draft.id ?? i} item={item} />
              ))}
            </>
          )}
          {!loading && !error && !result && (
            <div style={{ textAlign: "center", padding: "64px 0", color: "rgba(255,255,255,0.25)" }}>
              <PictureOutlined style={{ fontSize: 40, marginBottom: 12, display: "block" }} />
              <Text type="secondary">填写左侧设置后点击「开始生成」</Text>
            </div>
          )}
        </Col>
      </Row>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
cd frontend && npx tsc --noEmit
```

Expected: no errors from the new file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/platforms/xhs/agent-drafts-page.tsx
git commit -m "feat: add XhsAgentDraftsPage component"
```

---

## Task 7: Router and sidebar registration

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/components/layout/app-shell.tsx`

- [ ] **Step 1: Add the route to router.tsx**

In `frontend/src/app/router.tsx`:

1. Add import at the top with the other XHS page imports:

```typescript
import { XhsAgentDraftsPage } from "../pages/platforms/xhs/agent-drafts-page";
```

2. Add route inside the `<AppShell>` route group, before the catch-all `<Route path="/platforms/xhs/:section" ...>`:

```tsx
<Route path="/platforms/xhs/agent-drafts" element={<XhsAgentDraftsPage />} />
```

- [ ] **Step 2: Add sidebar entry to app-shell.tsx**

In `frontend/src/components/layout/app-shell.tsx`, `RobotOutlined` is already imported. Add the new entry to `mainNavItems` after the drafts entry:

```typescript
{ key: "/platforms/xhs/agent-drafts", icon: <RobotOutlined />, label: "Agent 草稿" },
```

Insert it after `{ key: "/platforms/xhs/drafts", icon: <FileTextOutlined />, label: "草稿工坊" }`.

- [ ] **Step 3: Build frontend**

```
cd frontend && npm run build
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Run all backend tests once more to confirm nothing broke**

```
python -m pytest tests/backend/ -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/router.tsx frontend/src/components/layout/app-shell.tsx
git commit -m "feat: register agent-drafts route and sidebar entry"
```

---

## Self-Review Checklist

After completing all tasks, verify:

- [ ] All 4 unit tests for `generate_agent_drafts` pass (Task 1)
- [ ] `_serialize_draft` returns `tags` key (Task 2)
- [ ] 5 integration tests for the endpoint pass (Task 3)
- [ ] TypeScript compiles with no new errors after types and api.ts changes (Tasks 4, 5)
- [ ] Frontend build passes after page + router changes (Tasks 6, 7)
- [ ] `python -m pytest tests/backend/ -v` all green (no regressions)
- [ ] Route `/platforms/xhs/agent-drafts` renders the new page in the browser
- [ ] Sidebar shows "Agent 草稿" entry in the right position (between 草稿工坊 and 发布中心)
- [ ] Submitting a request from the page creates drafts visible in 草稿工坊
