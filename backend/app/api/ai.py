from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import decrypt_text
from backend.app.models import AiDraft, AiGeneratedAsset, DraftAsset, ModelConfig, Task, User
from backend.app.schemas.common import paginated
from backend.app.services.ai_service import ImageAiClient, OpenAICompatibleImageClient, OpenAICompatibleTextClient, TextAiClient

router = APIRouter(prefix="/ai", tags=["ai"])


class RewriteNoteRequest(BaseModel):
    draft_id: int
    instruction: str = Field(default="", max_length=800)


class GenerateNoteRequest(BaseModel):
    platform: Literal["xhs", "douyin", "kuaishou", "weibo", "xianyu", "taobao"] = "xhs"
    topic: str = Field(min_length=1, max_length=300)
    reference: str = Field(default="", max_length=4000)
    instruction: str = Field(default="", max_length=1000)


class GenerateTitleRequest(BaseModel):
    title: str = Field(default="", max_length=300)
    body: str = Field(min_length=1, max_length=6000)
    count: int = Field(default=5, ge=1, le=10)


class GenerateTagsRequest(BaseModel):
    title: str = Field(default="", max_length=300)
    body: str = Field(min_length=1, max_length=6000)
    count: int = Field(default=8, ge=1, le=20)


class PolishTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    instruction: str = Field(default="", max_length=800)


class GenerateCoverRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1200)
    draft_id: Optional[int] = None
    size: str = Field(default="1024x1024", max_length=32)
    style: str = Field(default="clean", max_length=120)


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    reference_images: list[str] = Field(default_factory=list)
    save_to_assets: bool = True


class DescribeImageRequest(BaseModel):
    image_url: str = Field(min_length=1, max_length=4000)
    instruction: str = Field(default="", max_length=800)


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


def get_text_ai_client() -> TextAiClient:
    return OpenAICompatibleTextClient()


def get_image_ai_client() -> ImageAiClient:
    return OpenAICompatibleImageClient()


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


def _get_default_text_model(db: Session, current_user: User) -> ModelConfig:
    config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == current_user.id,
            ModelConfig.model_type == "text",
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default text model is not configured")
    return config


def _get_default_image_model(db: Session, current_user: User) -> ModelConfig:
    config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == current_user.id,
            ModelConfig.model_type == "image",
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default image model is not configured")
    return config


def _text_model_context(db: Session, current_user: User) -> tuple[ModelConfig, str]:
    model_config = _get_default_text_model(db, current_user)
    api_key = decrypt_text(model_config.encrypted_api_key) if model_config.encrypted_api_key else ""
    return model_config, api_key


def _image_model_context(db: Session, current_user: User) -> tuple[ModelConfig, str]:
    model_config = _get_default_image_model(db, current_user)
    api_key = decrypt_text(model_config.encrypted_api_key) if model_config.encrypted_api_key else ""
    return model_config, api_key


def _serialize_generated_asset(asset: AiGeneratedAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "draft_id": asset.draft_id,
        "prompt": asset.prompt,
        "model_name": asset.model_name,
        "params": asset.params or {},
        "file_path": asset.file_path,
        "created_at": asset.created_at.isoformat(),
    }


def _recorded_text_task(
    *,
    db: Session,
    current_user: User,
    platform: str,
    task_type: str,
    payload: dict[str, Any],
    action: Callable[[], Any],
):
    task = Task(
        user_id=current_user.id,
        platform=platform,
        task_type=task_type,
        status="running",
        progress=10,
        payload=payload,
    )
    db.add(task)
    db.flush()
    try:
        result = action()
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

    task.status = "completed"
    task.progress = 100
    return task, result


def _recorded_image_task(
    *,
    db: Session,
    current_user: User,
    task_type: str,
    payload: dict[str, Any],
    action: Callable[[], Any],
):
    task = Task(
        user_id=current_user.id,
        platform="xhs",
        task_type=task_type,
        status="running",
        progress=10,
        payload=payload,
    )
    db.add(task)
    db.flush()
    try:
        result = action()
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI image generation failed: {exc}") from exc

    task.status = "completed"
    task.progress = 100
    return task, result


@router.post("/rewrite-note")
def rewrite_note(
    payload: RewriteNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
):
    draft = db.get(AiDraft, payload.draft_id)
    if draft is None or draft.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    model_config, api_key = _text_model_context(db, current_user)
    task, rewritten_body = _recorded_text_task(
        db=db,
        current_user=current_user,
        platform=draft.platform,
        task_type="ai_rewrite",
        payload={"draft_id": draft.id, "model_config_id": model_config.id, "instruction": payload.instruction},
        action=lambda: text_ai_client.rewrite_note(
            model_config=model_config,
            api_key=api_key,
            title=draft.title,
            body=draft.body,
            instruction=payload.instruction,
        ),
    )
    draft.body = rewritten_body
    task.payload = {**(task.payload or {}), "result_draft_id": draft.id, "result_length": len(rewritten_body)}
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.post("/generate-note")
def generate_note(
    payload: GenerateNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
):
    model_config, api_key = _text_model_context(db, current_user)
    task, result = _recorded_text_task(
        db=db,
        current_user=current_user,
        platform=payload.platform,
        task_type="ai_generate_note",
        payload={"model_config_id": model_config.id, "topic": payload.topic},
        action=lambda: text_ai_client.generate_note(
            model_config=model_config,
            api_key=api_key,
            topic=payload.topic,
            reference=payload.reference,
            instruction=payload.instruction,
        ),
    )
    draft = AiDraft(
        user_id=current_user.id,
        platform=payload.platform,
        title=result.get("title") or payload.topic,
        body=result.get("body") or "",
    )
    db.add(draft)
    db.flush()
    task.payload = {**(task.payload or {}), "result_draft_id": draft.id}
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.post("/generate-title")
def generate_title(
    payload: GenerateTitleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
):
    model_config, api_key = _text_model_context(db, current_user)
    task, items = _recorded_text_task(
        db=db,
        current_user=current_user,
        platform="xhs",
        task_type="ai_generate_title",
        payload={"model_config_id": model_config.id, "count": payload.count},
        action=lambda: text_ai_client.generate_titles(
            model_config=model_config,
            api_key=api_key,
            title=payload.title,
            body=payload.body,
            count=payload.count,
        ),
    )
    task.payload = {**(task.payload or {}), "result_count": len(items)}
    db.commit()
    return {"items": items}


@router.post("/generate-tags")
def generate_tags(
    payload: GenerateTagsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
):
    model_config, api_key = _text_model_context(db, current_user)
    task, items = _recorded_text_task(
        db=db,
        current_user=current_user,
        platform="xhs",
        task_type="ai_generate_tags",
        payload={"model_config_id": model_config.id, "count": payload.count},
        action=lambda: text_ai_client.generate_tags(
            model_config=model_config,
            api_key=api_key,
            title=payload.title,
            body=payload.body,
            count=payload.count,
        ),
    )
    task.payload = {**(task.payload or {}), "result_count": len(items)}
    db.commit()
    return {"items": items}


@router.post("/polish-text")
def polish_text(
    payload: PolishTextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
):
    model_config, api_key = _text_model_context(db, current_user)
    task, text = _recorded_text_task(
        db=db,
        current_user=current_user,
        platform="xhs",
        task_type="ai_polish_text",
        payload={"model_config_id": model_config.id, "instruction": payload.instruction},
        action=lambda: text_ai_client.polish_text(
            model_config=model_config,
            api_key=api_key,
            text=payload.text,
            instruction=payload.instruction,
        ),
    )
    task.payload = {**(task.payload or {}), "result_length": len(text)}
    db.commit()
    return {"text": text}


@router.get("/images/assets")
def generated_image_assets(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assets = db.scalars(
        select(AiGeneratedAsset)
        .where(AiGeneratedAsset.user_id == current_user.id)
        .order_by(AiGeneratedAsset.created_at.desc(), AiGeneratedAsset.id.desc())
    ).all()
    return paginated([_serialize_generated_asset(asset) for asset in assets], page, page_size)


@router.delete("/images/assets/{asset_id}")
def delete_generated_image_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = db.get(AiGeneratedAsset, asset_id)
    if asset is None or asset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    db.delete(asset)
    db.commit()
    return {"id": asset_id, "status": "deleted"}


@router.post("/images/generate-cover")
def generate_cover(
    payload: GenerateCoverRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
):
    if payload.draft_id is not None:
        draft = db.get(AiDraft, payload.draft_id)
        if draft is None or draft.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    model_config, api_key = _image_model_context(db, current_user)
    task, result = _recorded_image_task(
        db=db,
        current_user=current_user,
        task_type="ai_image_generate_cover",
        payload={"model_config_id": model_config.id, "prompt": payload.prompt, "size": payload.size, "style": payload.style},
        action=lambda: image_ai_client.generate_cover(
            model_config=model_config,
            api_key=api_key,
            prompt=payload.prompt,
            size=payload.size,
            style=payload.style,
        ),
    )
    asset = AiGeneratedAsset(
        user_id=current_user.id,
        draft_id=payload.draft_id,
        prompt=payload.prompt,
        model_name=model_config.model_name,
        params={"size": payload.size, "style": payload.style, "raw": result.get("raw")},
        file_path=result.get("url") or "",
    )
    db.add(asset)
    db.flush()
    task.payload = {**(task.payload or {}), "asset_id": asset.id}
    db.commit()
    db.refresh(asset)
    return _serialize_generated_asset(asset)


@router.post("/images/generate")
def generate_image(
    payload: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
):
    model_config, api_key = _image_model_context(db, current_user)
    task, result = _recorded_image_task(
        db=db,
        current_user=current_user,
        task_type="ai_image_generate",
        payload={"model_config_id": model_config.id, "prompt": payload.prompt, "reference_images": payload.reference_images},
        action=lambda: image_ai_client.generate_image(
            model_config=model_config,
            api_key=api_key,
            prompt=payload.prompt,
            reference_images=payload.reference_images or None,
        ),
    )
    response_data: dict = {"url": result.get("url") or "", "raw": result.get("raw")}
    if payload.save_to_assets:
        asset = AiGeneratedAsset(
            user_id=current_user.id,
            prompt=payload.prompt,
            model_name=model_config.model_name,
            params={"reference_images": payload.reference_images, "raw": result.get("raw")},
            file_path=result.get("url") or "",
        )
        db.add(asset)
        db.flush()
        task.payload = {**(task.payload or {}), "asset_id": asset.id}
        db.commit()
        db.refresh(asset)
        response_data["asset"] = _serialize_generated_asset(asset)
    else:
        db.commit()
    return response_data


def _extract_message_parts(messages: list[_AgentMessage]) -> tuple[list[dict], list[str]]:
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


@router.post("/images/describe")
def describe_image(
    payload: DescribeImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
):
    model_config, api_key = _image_model_context(db, current_user)
    task, text = _recorded_image_task(
        db=db,
        current_user=current_user,
        task_type="ai_image_describe",
        payload={"model_config_id": model_config.id, "image_url": payload.image_url, "instruction": payload.instruction},
        action=lambda: image_ai_client.describe_image(
            model_config=model_config,
            api_key=api_key,
            image_url=payload.image_url,
            instruction=payload.instruction,
        ),
    )
    task.payload = {**(task.payload or {}), "result_length": len(text)}
    db.commit()
    return {"text": text}
