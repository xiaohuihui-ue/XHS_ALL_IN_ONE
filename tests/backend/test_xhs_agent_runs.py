from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.ai import get_image_ai_client, get_text_ai_client
from backend.app.core.database import Base, get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import encrypt_text
from backend.app.main import app
from backend.app.models import AccountCookieVersion, ModelConfig, Note, PlatformAccount, PublishAsset, PublishJob, User


def _make_test_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _seed_user_and_models(session, *, with_image_model=True, with_account=True):
    user = User(username="runner", email="runner@test.com", password_hash="x")
    session.add(user)
    session.flush()

    session.add(
        ModelConfig(
            user_id=user.id,
            name="default-text",
            model_type="text",
            provider="openai",
            model_name="gpt-test",
            base_url="http://fake-llm",
            encrypted_api_key=encrypt_text("sk-text"),
            is_default=True,
        )
    )
    if with_image_model:
        session.add(
            ModelConfig(
                user_id=user.id,
                name="default-image",
                model_type="image",
                provider="openai",
                model_name="image-test",
                base_url="http://fake-image",
                encrypted_api_key=encrypt_text("sk-image"),
                is_default=True,
            )
        )
    if with_account:
        session.add(
            PlatformAccount(
                user_id=user.id,
                platform="xhs",
                sub_type="creator",
                nickname="设计号",
                status="active",
            )
        )
    session.commit()
    session.refresh(user)
    return user


def _override_app(tmp_path, *, text_client, image_client=None, with_image_model=True, with_account=True):
    engine, SessionLocal = _make_test_db(tmp_path)
    db = SessionLocal()
    user = _seed_user_and_models(db, with_image_model=with_image_model, with_account=with_account)
    db.close()

    def override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
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


def test_xhs_agent_run_generates_draft_image_and_html_report(tmp_path):
    text_client = MagicMock()
    text_client.generate_draft_titles.return_value = {
        "titles": ["奶油风客厅改造"],
        "recommended_title": "奶油风客厅改造",
        "topics": ["室内设计"],
        "recommended_topic": "室内设计",
    }
    text_client.generate_single_draft.return_value = {
        "title": "奶油风客厅改造",
        "body": "用低饱和墙面、柔和灯光和弧形家具提升小客厅质感。",
        "tags": ["室内设计", "奶油风"],
        "cover_strategy": {"cover_goal": "吸引点击", "cover_type": "客厅全景", "visual_core": "柔和灯光", "title_space": "上方留白", "text_in_image": False},
        "image_prompt_spec": {"L1_publish_goal": "种草室内设计", "L2_topic": "奶油风客厅", "L12_negative_constraints": "不要文字和水印"},
        "publish_tips": "建议晚间发布。",
    }
    text_client.iterate_image_prompt.return_value = {
        "final_image_prompt": "cozy cream style living room, realistic interior design",
        "iteration_history": [],
        "total_rounds": 1,
    }
    image_client = MagicMock()
    image_client.generate_image_with_retry.return_value = {
        "url": "data:image/png;base64,abc",
        "iteration_history": [],
        "quality_check": {
            "need_retry": False,
            "vision_check_status": "skipped",
            "vision_check_message": "未执行视觉质检：当前模型未声明 vision 能力",
        },
        "final_image_prompt": "cozy cream style living room, realistic interior design",
    }

    engine, SessionLocal = _override_app(
        tmp_path, text_client=text_client, image_client=image_client, with_image_model=True, with_account=True
    )
    report_path = None
    try:
        client = TestClient(app)
        response = client.post("/api/xhs/agent/runs", json={
            "messages": [{"role": "user", "content": "生成一篇小红书室内设计笔记，配一张奶油风客厅封面图"}],
            "n": 1,
            "metadata": {"platform": "xhs", "output_requirements": "图片要真实、有室内设计质感"},
            "image_options": {"n": 1, "size": "1792x1024", "quality": "hd", "style": "natural"},
        })
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["result"]["created_count"] == 1
        assert body["result"]["items"][0]["final_image_prompt"] == "cozy cream style living room, realistic interior design"
        assert body["report"]["download_url"].endswith(".html")

        report_path = Path(body["report"]["file_path"])
        assert report_path.is_file()
        report_html = report_path.read_text(encoding="utf-8")
        assert "奶油风客厅改造" in report_html
        assert "cozy cream style living room" in report_html
        assert "未执行视觉质检" in report_html

        run_response = client.get(f"/api/xhs/agent/runs/{body['run_id']}")
        assert run_response.status_code == 200
        assert run_response.json()["run_id"] == body["run_id"]

        db = SessionLocal()
        try:
            publish_jobs = db.scalars(select(PublishJob)).all()
            assert publish_jobs == []
        finally:
            db.close()
    finally:
        if report_path and report_path.exists():
            report_path.unlink()
        _cleanup(engine, SessionLocal)


def test_xhs_agent_run_requires_default_text_model(tmp_path):
    text_client = MagicMock()
    engine, SessionLocal = _make_test_db(tmp_path)
    db = SessionLocal()
    user = User(username="runner2", email="runner2@test.com", password_hash="x")
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
    app.dependency_overrides[get_text_ai_client] = lambda: text_client
    try:
        client = TestClient(app)
        response = client.post("/api/xhs/agent/runs", json={
            "messages": [{"role": "user", "content": "生成室内设计笔记"}],
            "metadata": {"platform": "xhs"},
            "image_options": {"n": 0},
        })
        assert response.status_code == 400
        assert "text model" in response.json()["detail"].lower()
    finally:
        _cleanup(engine, SessionLocal)


def test_xhs_agent_run_includes_research_references_in_prompt_and_report(tmp_path):
    text_client = MagicMock()
    text_client.generate_draft_titles.return_value = {
        "titles": ["Cream living room ideas"],
        "recommended_title": "Cream living room ideas",
        "topics": ["interior design"],
        "recommended_topic": "interior design",
    }
    text_client.generate_single_draft.return_value = {
        "title": "Cream living room ideas",
        "body": "Use warm lighting and soft materials.",
        "tags": ["interior", "livingroom"],
        "cover_strategy": {},
        "image_prompt_spec": {},
        "publish_tips": "Review manually before publishing.",
    }

    engine, SessionLocal = _override_app(
        tmp_path, text_client=text_client, image_client=MagicMock(), with_image_model=False, with_account=True
    )
    report_path = None
    try:
        db = SessionLocal()
        user = db.query(User).first()
        account = db.query(PlatformAccount).first()
        note = Note(
            user_id=user.id,
            platform_account_id=account.id,
            platform="xhs",
            note_id="note-research-001",
            title="Small living room storage reference",
            content="A saved note about cream living room storage and lighting.",
            author_name="designer",
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        db.close()

        client = TestClient(app)
        response = client.post("/api/xhs/agent/runs", json={
            "messages": [{"role": "user", "content": "Create one XHS draft about cream living rooms."}],
            "n": 1,
            "metadata": {
                "platform": "xhs",
                "research": {
                    "keywords": ["cream living room", "small apartment"],
                    "reference_note_ids": [note.id],
                },
            },
            "image_options": {"n": 0},
        })
        assert response.status_code == 200
        body = response.json()
        assert body["research"]["keywords"] == ["cream living room", "small apartment"]
        assert body["research"]["reference_notes"][0]["id"] == note.id

        title_messages = text_client.generate_draft_titles.call_args.kwargs["messages"]
        assert "Small living room storage reference" in str(title_messages)
        assert "cream living room storage" in str(title_messages)

        report_path = Path(body["report"]["file_path"])
        report_html = report_path.read_text(encoding="utf-8")
        assert "Small living room storage reference" in report_html
        assert "cream living room" in report_html
    finally:
        if report_path and report_path.exists():
            report_path.unlink()
        _cleanup(engine, SessionLocal)


def test_xhs_agent_run_confirm_creates_publish_job_after_manual_confirmation(tmp_path):
    text_client = MagicMock()
    text_client.generate_draft_titles.return_value = {
        "titles": ["Manual publish draft"],
        "recommended_title": "Manual publish draft",
        "topics": ["interior design"],
        "recommended_topic": "interior design",
    }
    text_client.generate_single_draft.return_value = {
        "title": "Manual publish draft",
        "body": "Draft body for manual publish confirmation.",
        "tags": ["interior"],
        "cover_strategy": {},
        "image_prompt_spec": {},
        "publish_tips": "",
    }
    text_client.iterate_image_prompt.return_value = {
        "final_image_prompt": "manual publish image prompt",
        "iteration_history": [],
        "total_rounds": 1,
    }
    image_client = MagicMock()
    image_client.generate_image_with_retry.return_value = {
        "url": "data:image/png;base64,abc",
        "iteration_history": [],
        "quality_check": {"need_retry": False},
        "final_image_prompt": "manual publish image prompt",
    }

    engine, SessionLocal = _override_app(
        tmp_path, text_client=text_client, image_client=image_client, with_image_model=True, with_account=True
    )
    report_path = None
    try:
        client = TestClient(app)
        run_response = client.post("/api/xhs/agent/runs", json={
            "messages": [{"role": "user", "content": "Create a draft that will be manually confirmed."}],
            "n": 1,
            "metadata": {"platform": "xhs"},
            "image_options": {"n": 1},
        })
        assert run_response.status_code == 200
        run_body = run_response.json()
        report_path = Path(run_body["report"]["file_path"])

        db = SessionLocal()
        account = db.query(PlatformAccount).first()
        db.close()

        confirm_response = client.post(f"/api/xhs/agent/runs/{run_body['run_id']}/confirm", json={
            "platform_account_id": account.id,
            "draft_ids": [run_body["result"]["items"][0]["draft"]["id"]],
            "publish_mode": "immediate",
        })
        assert confirm_response.status_code == 200
        confirm_body = confirm_response.json()
        assert confirm_body["created_count"] == 1
        assert confirm_body["items"][0]["status"] == "pending"

        db = SessionLocal()
        try:
            jobs = db.scalars(select(PublishJob)).all()
            assert len(jobs) == 1
            assert jobs[0].status == "pending"
            assert jobs[0].source_draft_id == run_body["result"]["items"][0]["draft"]["id"]
            assets = db.scalars(select(PublishAsset).where(PublishAsset.publish_job_id == jobs[0].id)).all()
            assert len(assets) == 1
            assert assets[0].upload_status == "pending"
        finally:
            db.close()
    finally:
        if report_path and report_path.exists():
            report_path.unlink()
        _cleanup(engine, SessionLocal)


class FakeAgentSearchAdapter:
    calls = []

    def __init__(self, cookies):
        self.cookies = cookies

    def search_note(self, keyword, page=1, **kwargs):
        self.__class__.calls.append({"cookies": self.cookies, "keyword": keyword, "page": page, **kwargs})
        return (
            True,
            "ok",
            {
                "success": True,
                "data": {
                    "items": [
                        {
                            "model_type": "note",
                            "xsec_token": "low-token",
                            "note_card": {
                                "note_id": "low-engagement-note",
                                "display_title": "Low engagement cream room",
                                "desc": "A lower engagement reference.",
                                "user": {"nickname": "low author"},
                                "interact_info": {"liked_count": "10", "collected_count": "1", "comment_count": "0"},
                            },
                        },
                        {
                            "model_type": "note",
                            "xsec_token": "top-token",
                            "note_card": {
                                "note_id": "top-engagement-note",
                                "display_title": "Top cream living room reference",
                                "desc": "A high engagement cream living room with warm lighting.",
                                "user": {"nickname": "top author"},
                                "interact_info": {"liked_count": "200", "collected_count": "50", "comment_count": "20"},
                            },
                        },
                    ]
                },
            },
        )


def test_xhs_agent_run_searches_saves_and_uses_research_notes(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    text_client = MagicMock()
    text_client.generate_draft_titles.return_value = {
        "titles": ["Cream room search based draft"],
        "recommended_title": "Cream room search based draft",
        "topics": ["interior design"],
        "recommended_topic": "interior design",
    }
    text_client.generate_single_draft.return_value = {
        "title": "Cream room search based draft",
        "body": "Use the searched references to plan a warmer room.",
        "tags": ["interior"],
        "cover_strategy": {},
        "image_prompt_spec": {},
        "publish_tips": "",
    }

    engine, SessionLocal = _override_app(
        tmp_path, text_client=text_client, image_client=MagicMock(), with_image_model=False, with_account=False
    )
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeAgentSearchAdapter
    report_path = None
    try:
        db = SessionLocal()
        user = db.query(User).first()
        account = PlatformAccount(
            user_id=user.id,
            platform="xhs",
            sub_type="pc",
            external_user_id="agent-search-user",
            nickname="Agent search account",
            status="active",
        )
        db.add(account)
        db.flush()
        db.add(
            AccountCookieVersion(
                platform_account_id=account.id,
                encrypted_cookies=encrypt_text('{"a1":"agent-a1","web_session":"agent-session"}'),
            )
        )
        db.commit()
        db.refresh(account)
        db.close()

        FakeAgentSearchAdapter.calls = []
        client = TestClient(app)
        response = client.post("/api/xhs/agent/runs", json={
            "messages": [{"role": "user", "content": "Create one XHS draft about cream living rooms."}],
            "n": 1,
            "metadata": {
                "platform": "xhs",
                "research": {
                    "keywords": ["cream living room"],
                    "search_account_id": account.id,
                    "search_limit": 1,
                    "auto_save": True,
                },
            },
            "image_options": {"n": 0},
        })
        assert response.status_code == 200
        body = response.json()
        assert body["research"]["search"]["saved_count"] == 1
        assert body["research"]["search"]["saved_notes"][0]["note_id"] == "top-engagement-note"
        assert body["research"]["reference_notes"][0]["title"] == "Top cream living room reference"
        assert FakeAgentSearchAdapter.calls[0]["cookies"] == "a1=agent-a1; web_session=agent-session"

        title_messages = text_client.generate_draft_titles.call_args.kwargs["messages"]
        assert "Top cream living room reference" in str(title_messages)
        assert "high engagement cream living room" in str(title_messages)

        db = SessionLocal()
        try:
            notes = db.query(Note).all()
            assert len(notes) == 1
            assert notes[0].note_id == "top-engagement-note"
            assert notes[0].raw_json["agent_source"]["keywords"] == ["cream living room"]
        finally:
            db.close()

        report_path = Path(body["report"]["file_path"])
        report_html = report_path.read_text(encoding="utf-8")
        assert "cream living room" in report_html
        assert "top-engagement-note" in report_html
        assert "Top cream living room reference" in report_html
    finally:
        if report_path and report_path.exists():
            report_path.unlink()
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)
        _cleanup(engine, SessionLocal)
