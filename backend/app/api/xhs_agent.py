from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.ai import get_image_ai_client, get_text_ai_client
from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import Task, User
from backend.app.services.ai_service import ImageAiClient, TextAiClient
from backend.app.services.xhs_agent_service import XhsAgentService

router = APIRouter(prefix="/xhs/agent", tags=["xhs-agent"])


class AgentImageUrlPart(BaseModel):
    url: str


class AgentContentPart(BaseModel):
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: AgentImageUrlPart | None = None


class AgentMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[AgentContentPart]


class AgentMetadata(BaseModel):
    platform: Literal["xhs"]
    account_id: int | None = None
    output_requirements: str | None = None
    save_to_drafts: str | None = None
    research: "AgentResearchOptions | None" = None


class AgentResearchOptions(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    reference_note_ids: list[int] = Field(default_factory=list)
    search_account_id: int | None = None
    search_limit: int = Field(default=0, ge=0, le=10)
    auto_save: bool = False


class AgentImageOptions(BaseModel):
    model: str | None = None
    n: int = Field(default=1, ge=0, le=3)
    size: str | None = None
    quality: str | None = None
    style: str | None = None
    response_format: str | None = None


class XhsAgentRunRequest(BaseModel):
    model: str | None = None
    messages: list[AgentMessage] = Field(min_length=1)
    n: int = Field(default=1, ge=1, le=3)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stream: Literal[False] | None = None
    response_format: dict[str, Any] | None = None
    metadata: AgentMetadata = Field(default_factory=lambda: AgentMetadata(platform="xhs"))
    image_options: AgentImageOptions = Field(default_factory=AgentImageOptions)
    user: str | None = None


class ConfirmAgentRunRequest(BaseModel):
    platform_account_id: int | None = None
    draft_ids: list[int] | None = None
    publish_mode: Literal["immediate", "scheduled"] = "immediate"
    scheduled_at: datetime | None = None
    topics: list[str] | None = None
    location: str | None = None
    privacy_type: int | None = Field(default=None, ge=0, le=1)
    is_private: bool | None = None


def _extract_message_parts(messages: list[AgentMessage]) -> tuple[list[dict[str, Any]], list[str]]:
    plain: list[dict[str, Any]] = []
    ref_urls: list[str] = []
    for message in messages:
        if isinstance(message.content, str):
            plain.append({"role": message.role, "content": message.content})
            continue

        parts: list[dict[str, Any]] = []
        for part in message.content:
            if part.type == "text":
                parts.append({"type": "text", "text": part.text or ""})
            elif part.type == "image_url" and part.image_url:
                url = part.image_url.url
                parts.append({"type": "image_url", "image_url": {"url": url}})
                ref_urls.append(url)
        plain.append({"role": message.role, "content": parts})
    return plain, ref_urls


@router.post("/runs")
def create_agent_run(
    payload: XhsAgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
    pc_adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    messages, reference_image_urls = _extract_message_parts(payload.messages)
    service = XhsAgentService(
        db=db,
        current_user=current_user,
        text_ai_client=text_ai_client,
        image_ai_client=image_ai_client,
        pc_adapter_factory=pc_adapter_factory,
    )
    return service.run(
        messages=messages,
        reference_image_urls=reference_image_urls,
        n=payload.n,
        temperature=payload.temperature,
        top_p=payload.top_p,
        output_requirements=payload.metadata.output_requirements,
        research_options=payload.metadata.research.model_dump() if payload.metadata.research else None,
        image_options=payload.image_options.model_dump(),
        model=payload.model,
        account_id=payload.metadata.account_id,
    )


@router.get("/runs/{run_id}")
def get_agent_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalars(
        select(Task).where(
            Task.id == run_id,
            Task.user_id == current_user.id,
            Task.platform == "xhs",
            Task.task_type == "xhs_agent_run",
        )
    ).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    payload = task.payload or {}
    return {
        "run_id": task.id,
        "status": task.status,
        "progress": task.progress,
        **payload,
    }


@router.post("/runs/{run_id}/confirm")
def confirm_agent_run(
    run_id: int,
    payload: ConfirmAgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_ai_client: TextAiClient = Depends(get_text_ai_client),
    image_ai_client: ImageAiClient = Depends(get_image_ai_client),
):
    service = XhsAgentService(
        db=db,
        current_user=current_user,
        text_ai_client=text_ai_client,
        image_ai_client=image_ai_client,
    )
    return service.confirm_run(
        run_id=run_id,
        platform_account_id=payload.platform_account_id,
        draft_ids=payload.draft_ids,
        publish_mode=payload.publish_mode,
        scheduled_at=payload.scheduled_at,
        topics=payload.topics,
        location=payload.location,
        privacy_type=payload.privacy_type,
        is_private=payload.is_private,
    )
