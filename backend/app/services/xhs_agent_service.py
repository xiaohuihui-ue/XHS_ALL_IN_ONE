from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.platforms.xhs.crawl import _data_items, _save_normalized_notes
from backend.app.api.platforms.xhs.pc import _get_owned_pc_account_cookies, _normalize_search_item
from backend.app.core.security import decrypt_text
from backend.app.models import (
    MODEL_CAPABILITY_IMAGE_GENERATION,
    MODEL_CAPABILITY_TEXT_GENERATION,
    AiDraft,
    AiGeneratedAsset,
    DraftAsset,
    ModelConfig,
    Note,
    PlatformAccount,
    PublishAsset,
    PublishJob,
    Task,
    User,
    model_has_capability,
    normalize_model_capabilities,
)
from backend.app.services.agent_report_service import write_xhs_agent_report
from backend.app.services.ai_service import ImageAiClient, TextAiClient
from backend.app.services.asset_downloader import download_asset_to_local


def _serialize_draft(draft: AiDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "platform": draft.platform,
        "title": draft.title,
        "body": draft.body,
        "tags": draft.tags or [],
        "source_note_id": draft.source_note_id,
        "created_at": draft.created_at.isoformat(),
    }


def _serialize_draft_asset(asset: DraftAsset) -> dict[str, Any]:
    display_url = f"/api/files/media/{asset.local_path}" if asset.local_path else asset.url
    return {
        "id": asset.id,
        "draft_id": asset.draft_id,
        "asset_type": asset.asset_type,
        "url": display_url,
        "local_path": asset.local_path,
        "sort_order": asset.sort_order,
    }


def _text_from_messages(messages: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(str(part.get("text") or ""))
    return "\n".join(text for text in texts if text).strip()


def _clean_topics(topics: list[str] | None) -> list[str]:
    if topics is None:
        return []
    return [topic.strip() for topic in topics if topic and topic.strip()]


def _model_context(
    db: Session,
    current_user: User,
    model_type: str,
    required_capability: str | None = None,
) -> tuple[ModelConfig, str]:
    model_config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == current_user.id,
            ModelConfig.model_type == model_type,
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if model_config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Default {model_type} model is not configured")
    if required_capability and not model_has_capability(model_config, required_capability):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Default {model_type} model does not support {required_capability}")
    api_key = decrypt_text(model_config.encrypted_api_key) if model_config.encrypted_api_key else ""
    return model_config, api_key


class XhsAgentService:
    def __init__(
        self,
        *,
        db: Session,
        current_user: User,
        text_ai_client: TextAiClient,
        image_ai_client: ImageAiClient,
        pc_adapter_factory: Any | None = None,
    ) -> None:
        self.db = db
        self.current_user = current_user
        self.text_ai_client = text_ai_client
        self.image_ai_client = image_ai_client
        self.pc_adapter_factory = pc_adapter_factory

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        reference_image_urls: list[str],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        research_options: dict[str, Any] | None,
        image_options: dict[str, Any],
        model: str | None,
        account_id: int | None,
    ) -> dict[str, Any]:
        text_model_config, text_api_key = _model_context(
            self.db,
            self.current_user,
            "text",
            MODEL_CAPABILITY_TEXT_GENERATION,
        )
        image_count = int(image_options.get("n") or 0)
        image_model_config: ModelConfig | None = None
        image_api_key = ""
        if image_count > 0:
            image_model_config, image_api_key = _model_context(
                self.db,
                self.current_user,
                "image",
                MODEL_CAPABILITY_IMAGE_GENERATION,
            )

        account_check = self._account_check(account_id)
        research = self._load_research(research_options)
        generation_messages = self._append_research_context(messages, research)
        model_check = {
            "text_model_config_id": text_model_config.id,
            "text_model_name": text_model_config.model_name,
            "image_model_config_id": image_model_config.id if image_model_config else None,
            "image_model_name": image_model_config.model_name if image_model_config else None,
            "text_model_capabilities": normalize_model_capabilities(text_model_config.model_type, text_model_config.capabilities, strict=False),
            "image_model_capabilities": normalize_model_capabilities(image_model_config.model_type, image_model_config.capabilities, strict=False) if image_model_config else [],
            "requested_model": model or "default",
        }

        task = Task(
            user_id=self.current_user.id,
            platform="xhs",
            task_type="xhs_agent_run",
            status="running",
            progress=10,
            payload={
                "request": {
                    "n": n,
                    "image_options": image_options,
                    "reference_image_count": len(reference_image_urls),
                    "research": research,
                },
                "account_check": account_check,
                "model_check": model_check,
            },
        )
        self.db.add(task)
        self.db.flush()

        try:
            result = self._generate_items(
                messages=generation_messages,
                reference_image_urls=reference_image_urls,
                n=n,
                temperature=temperature,
                top_p=top_p,
                output_requirements=output_requirements,
                image_count=image_count,
                image_options=image_options,
                text_model_config=text_model_config,
                text_api_key=text_api_key,
                image_model_config=image_model_config,
                image_api_key=image_api_key,
            )
        except HTTPException:
            task.status = "failed"
            task.progress = 100
            self.db.commit()
            raise
        except Exception as exc:
            task.status = "failed"
            task.progress = 100
            task.payload = {**(task.payload or {}), "error": str(exc)}
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"XHS agent run failed: {exc}") from exc

        publish_preview = {
            "auto_publish": False,
            "message": "Agent 仅生成草稿和素材；真实发布需要在发布中心人工确认。",
        }
        run_payload = {
            "run_id": task.id,
            "status": "completed",
            "account_check": account_check,
            "model_check": model_check,
            "research": research,
            "publish_preview": publish_preview,
            "result": result,
        }
        report = write_xhs_agent_report(self.current_user, run_payload)
        run_payload["report"] = report

        task.status = "completed"
        task.progress = 100
        task.payload = run_payload
        self.db.commit()
        self.db.refresh(task)
        return run_payload

    def confirm_run(
        self,
        *,
        run_id: int,
        platform_account_id: int | None,
        draft_ids: list[int] | None,
        publish_mode: str,
        scheduled_at: datetime | None,
        topics: list[str] | None,
        location: str | None,
        privacy_type: int | None,
        is_private: bool | None,
    ) -> dict[str, Any]:
        task = self.db.scalars(
            select(Task).where(
                Task.id == run_id,
                Task.user_id == self.current_user.id,
                Task.platform == "xhs",
                Task.task_type == "xhs_agent_run",
            )
        ).first()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

        account_id = None
        if platform_account_id is not None:
            account = self.db.get(PlatformAccount, platform_account_id)
            if account is None or account.user_id != self.current_user.id or account.platform != "xhs":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform account not found")
            account_id = account.id

        payload = task.payload or {}
        result_items = (payload.get("result") or {}).get("items") or []
        allowed_draft_ids = {
            int(item["draft"]["id"])
            for item in result_items
            if isinstance(item, dict) and isinstance(item.get("draft"), dict) and item["draft"].get("id") is not None
        }
        selected_ids = [int(draft_id) for draft_id in (draft_ids or sorted(allowed_draft_ids))]
        if not selected_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No drafts selected for publish confirmation")

        invalid_ids = [draft_id for draft_id in selected_ids if draft_id not in allowed_draft_ids]
        if invalid_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected drafts are not part of this agent run")

        publish_options = self._build_publish_options(
            topics=topics,
            location=location,
            privacy_type=privacy_type,
            is_private=is_private,
        )
        items: list[dict[str, Any]] = []
        for draft_id in selected_ids:
            draft = self.db.get(AiDraft, draft_id)
            if draft is None or draft.user_id != self.current_user.id or draft.platform != "xhs":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

            options = dict(publish_options)
            if draft.tags:
                options["draft_tags"] = draft.tags
            job = PublishJob(
                user_id=self.current_user.id,
                platform_account_id=account_id,
                source_draft_id=draft.id,
                platform=draft.platform,
                title=draft.title,
                body=draft.body,
                publish_mode=publish_mode,
                publish_options=json.dumps(options, ensure_ascii=False, separators=(",", ":")),
                scheduled_at=scheduled_at,
                status="pending",
            )
            self.db.add(job)
            self.db.flush()

            draft_assets = self.db.scalars(
                select(DraftAsset)
                .where(DraftAsset.draft_id == draft.id)
                .order_by(DraftAsset.sort_order.asc(), DraftAsset.id.asc())
            ).all()
            for draft_asset in draft_assets:
                file_path = f"/api/files/media/{draft_asset.local_path}" if draft_asset.local_path else draft_asset.url
                self.db.add(
                    PublishAsset(
                        publish_job_id=job.id,
                        asset_type=draft_asset.asset_type,
                        file_path=file_path,
                        upload_status="pending",
                    )
                )
            items.append(self._serialize_publish_job(job))

        confirmation = {
            "created_count": len(items),
            "publish_job_ids": [item["id"] for item in items],
            "draft_ids": selected_ids,
            "publish_mode": publish_mode,
        }
        task.payload = {**payload, "publish_confirmation": confirmation}
        self.db.commit()
        return {
            "run_id": task.id,
            "created_count": len(items),
            "items": items,
            "message": "Publish jobs created for manual confirmation; no automatic publish was executed.",
        }

    def _account_check(self, account_id: int | None) -> dict[str, Any]:
        statement = select(PlatformAccount).where(
            PlatformAccount.user_id == self.current_user.id,
            PlatformAccount.platform == "xhs",
        )
        accounts = self.db.scalars(statement.order_by(PlatformAccount.created_at.desc())).all()
        selected = None
        if account_id is not None:
            selected = next((account for account in accounts if account.id == account_id), None)
            if selected is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="XHS account not found")
        elif accounts:
            selected = accounts[0]
        warnings = [] if selected else ["No XHS account is configured; publish preparation is disabled."]
        return {
            "account_count": len(accounts),
            "selected_account_id": selected.id if selected else None,
            "selected_account_nickname": selected.nickname if selected else "",
            "selected_account_status": selected.status if selected else "",
            "warnings": warnings,
        }

    def _load_research(self, research_options: dict[str, Any] | None) -> dict[str, Any]:
        research_options = research_options or {}
        keywords = [keyword.strip() for keyword in (research_options.get("keywords") or []) if str(keyword).strip()]
        note_ids = [int(note_id) for note_id in (research_options.get("reference_note_ids") or [])]
        reference_notes: list[dict[str, Any]] = []
        if note_ids:
            notes = self.db.scalars(
                select(Note).where(Note.user_id == self.current_user.id, Note.id.in_(note_ids))
            ).all()
            notes_by_id = {note.id: note for note in notes}
            missing_ids = [note_id for note_id in note_ids if note_id not in notes_by_id]
            if missing_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference note not found")
            for note_id in note_ids:
                note = notes_by_id[note_id]
                reference_notes.append(
                    {
                        "id": note.id,
                        "note_id": note.note_id,
                        "title": note.title,
                        "content": note.content,
                        "author_name": note.author_name,
                    }
                )
        search = self._search_and_save_research(research_options, keywords)
        seen_note_ids = {note["id"] for note in reference_notes}
        for note in search.get("saved_notes", []):
            if note["id"] not in seen_note_ids:
                reference_notes.append(note)
                seen_note_ids.add(note["id"])
        research: dict[str, Any] = {"keywords": keywords, "reference_notes": reference_notes}
        if search.get("enabled"):
            research["search"] = search
        return research

    def _search_and_save_research(self, research_options: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
        auto_save = bool(research_options.get("auto_save"))
        search_limit = int(research_options.get("search_limit") or 0)
        search_account_id = research_options.get("search_account_id")
        if not auto_save and not search_account_id:
            return {"enabled": False}
        if not keywords:
            return {"enabled": False}
        if search_account_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="search_account_id is required for Agent research search")
        if self.pc_adapter_factory is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="XHS PC search adapter is not configured")

        account = self.db.get(PlatformAccount, int(search_account_id))
        if (
            account is None
            or account.user_id != self.current_user.id
            or account.platform != "xhs"
            or account.sub_type != "pc"
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="XHS PC account not found")

        cookies = _get_owned_pc_account_cookies(self.db, self.current_user, account.id)
        candidates: list[dict[str, Any]] = []
        for keyword in keywords:
            success, message, raw_payload = self.pc_adapter_factory(cookies).search_note(keyword, page=1)
            if not success:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message or "XHS note search failed")
            for raw_item in _data_items(raw_payload):
                normalized = _normalize_search_item(raw_item)
                if not normalized.get("note_id"):
                    continue
                normalized["agent_search_keyword"] = keyword
                candidates.append(normalized)

        def score(item: dict[str, Any]) -> int:
            return int(item.get("likes") or 0) + int(item.get("collects") or 0) + int(item.get("comments") or 0)

        unique_candidates: dict[str, dict[str, Any]] = {}
        for item in sorted(candidates, key=score, reverse=True):
            note_id = str(item.get("note_id") or "")
            if note_id and note_id not in unique_candidates:
                unique_candidates[note_id] = item

        selected = list(unique_candidates.values())[:search_limit or len(unique_candidates)]
        saved_notes = _save_normalized_notes(self.db, account, selected) if auto_save and selected else []
        saved_summary: list[dict[str, Any]] = []
        for note in saved_notes:
            raw_json = dict(note.raw_json) if isinstance(note.raw_json, dict) else {}
            raw_json["agent_source"] = {
                "type": "xhs_agent_research",
                "keywords": keywords,
                "search_account_id": account.id,
            }
            note.raw_json = raw_json
            saved_summary.append(
                {
                    "id": note.id,
                    "note_id": note.note_id,
                    "title": note.title,
                    "content": note.content,
                    "author_name": note.author_name,
                }
            )
        if saved_notes:
            self.db.commit()

        return {
            "enabled": True,
            "account_id": account.id,
            "keywords": keywords,
            "candidate_count": len(unique_candidates),
            "saved_count": len(saved_summary),
            "candidates": [
                {
                    "keyword": item.get("agent_search_keyword") or "",
                    "note_id": item.get("note_id") or "",
                    "title": item.get("title") or "",
                    "content": item.get("content") or "",
                    "author_name": item.get("author_name") or "",
                    "note_url": item.get("note_url") or "",
                    "likes": item.get("likes") or 0,
                    "collects": item.get("collects") or 0,
                    "comments": item.get("comments") or 0,
                }
                for item in selected
            ],
            "saved_notes": saved_summary,
        }

    def _append_research_context(self, messages: list[dict[str, Any]], research: dict[str, Any]) -> list[dict[str, Any]]:
        keywords = research.get("keywords") or []
        notes = research.get("reference_notes") or []
        if not keywords and not notes:
            return messages

        lines = ["Research references for this Xiaohongshu draft:"]
        if keywords:
            lines.append("Keywords: " + ", ".join(keywords))
        if notes:
            lines.append("Saved notes:")
            for note in notes:
                title = note.get("title") or ""
                content = note.get("content") or ""
                author = note.get("author_name") or ""
                lines.append(f"- {title} by {author}: {content}")
        return [*messages, {"role": "system", "content": "\n".join(lines)}]

    def _build_publish_options(
        self,
        *,
        topics: list[str] | None,
        location: str | None,
        privacy_type: int | None,
        is_private: bool | None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        cleaned_topics = _clean_topics(topics)
        if cleaned_topics:
            options["topics"] = cleaned_topics
        if location and location.strip():
            options["location"] = location.strip()
        if is_private is not None:
            options["is_private"] = is_private
            options["privacy_type"] = 1 if is_private else 0
        elif privacy_type is not None:
            options["privacy_type"] = privacy_type
            options["is_private"] = privacy_type == 1
        return options

    def _serialize_publish_job(self, job: PublishJob) -> dict[str, Any]:
        try:
            publish_options = json.loads(job.publish_options or "{}")
        except json.JSONDecodeError:
            publish_options = {}
        return {
            "id": job.id,
            "platform_account_id": job.platform_account_id,
            "source_draft_id": job.source_draft_id,
            "platform": job.platform,
            "title": job.title,
            "body": job.body,
            "publish_mode": job.publish_mode,
            "publish_options": publish_options,
            "status": job.status,
            "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
            "created_at": job.created_at.isoformat(),
        }

    def _generate_items(
        self,
        *,
        messages: list[dict[str, Any]],
        reference_image_urls: list[str],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        image_count: int,
        image_options: dict[str, Any],
        text_model_config: ModelConfig,
        text_api_key: str,
        image_model_config: ModelConfig | None,
        image_api_key: str,
    ) -> dict[str, Any]:
        title_result = self.text_ai_client.generate_draft_titles(
            model_config=text_model_config,
            api_key=text_api_key,
            messages=messages,
            n=n,
            temperature=temperature,
            top_p=top_p,
        )
        fallback_title = _text_from_messages(messages)[:80] or "小红书内容笔记"
        titles = [title for title in (title_result.get("titles") or []) if title]
        if not titles:
            titles = [title_result.get("recommended_title") or fallback_title]

        items: list[dict[str, Any]] = []
        created_count = 0
        failed_count = 0
        for index, title in enumerate(titles[:n]):
            try:
                item = self._generate_one_item(
                    title=title,
                    messages=messages,
                    reference_image_urls=reference_image_urls,
                    temperature=temperature,
                    top_p=top_p,
                    output_requirements=output_requirements,
                    image_count=image_count,
                    image_options=image_options,
                    text_model_config=text_model_config,
                    text_api_key=text_api_key,
                    image_model_config=image_model_config,
                    image_api_key=image_api_key,
                    sort_index=index,
                )
                created_count += 1
            except Exception as exc:
                failed_count += 1
                item = {"draft": None, "assets": [], "status": "failed", "errors": [str(exc)]}
            items.append(item)
        return {"items": items, "created_count": created_count, "failed_count": failed_count}

    def _generate_one_item(
        self,
        *,
        title: str,
        messages: list[dict[str, Any]],
        reference_image_urls: list[str],
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        image_count: int,
        image_options: dict[str, Any],
        text_model_config: ModelConfig,
        text_api_key: str,
        image_model_config: ModelConfig | None,
        image_api_key: str,
        sort_index: int,
    ) -> dict[str, Any]:
        draft_data = self.text_ai_client.generate_single_draft(
            model_config=text_model_config,
            api_key=text_api_key,
            messages=messages,
            title=title,
            temperature=temperature,
            top_p=top_p,
            output_requirements=output_requirements,
        )
        tags = [{"name": tag} for tag in (draft_data.get("tags") or [])]
        draft = AiDraft(
            user_id=self.current_user.id,
            platform="xhs",
            title=draft_data.get("title") or title,
            body=draft_data.get("body") or "",
            tags=tags,
        )
        self.db.add(draft)
        self.db.flush()

        assets: list[dict[str, Any]] = []
        errors: list[str] = []
        final_image_prompt = ""
        iteration_history: list[dict[str, Any]] = []
        quality_check: dict[str, Any] = {}

        if image_count > 0 and image_model_config is not None:
            for img_index in range(image_count):
                try:
                    iter_result = self.text_ai_client.iterate_image_prompt(
                        model_config=text_model_config,
                        api_key=text_api_key,
                        image_prompt_spec=draft_data.get("image_prompt_spec") or {},
                        cover_strategy=draft_data.get("cover_strategy") or {},
                        draft_body=draft.body,
                        reference_image_urls=reference_image_urls,
                        max_iterations=3,
                        target_score=4.5,
                    )
                    final_image_prompt = iter_result.get("final_image_prompt") or draft.title
                    iteration_history.extend(iter_result.get("iteration_history") or [])
                except Exception as exc:
                    errors.append(f"Image prompt iteration failed, using fallback: {exc}")
                    final_image_prompt = draft.title

                image_result = self.image_ai_client.generate_image_with_retry(
                    prompt=final_image_prompt,
                    reference_images=reference_image_urls if reference_image_urls else None,
                    image_model_config=image_model_config,
                    image_api_key=image_api_key,
                    text_model_config=text_model_config,
                    text_api_key=text_api_key,
                    topic=draft.title,
                    max_retries=2,
                    size=image_options.get("size"),
                    quality=image_options.get("quality"),
                    style=image_options.get("style"),
                    response_format=image_options.get("response_format"),
                )
                final_image_prompt = image_result.get("final_image_prompt") or final_image_prompt
                image_url = image_result.get("url") or ""
                local_name = download_asset_to_local(image_url, self.current_user.id, "image")
                local_file_path = f"/api/files/media/{local_name}" if local_name else image_url

                self.db.add(
                    AiGeneratedAsset(
                        user_id=self.current_user.id,
                        draft_id=draft.id,
                        prompt=final_image_prompt,
                        model_name=image_model_config.model_name,
                        params={
                            "size": image_options.get("size"),
                            "quality": image_options.get("quality"),
                            "style": image_options.get("style"),
                            "response_format": image_options.get("response_format"),
                            "raw": image_result.get("raw"),
                        },
                        file_path=local_file_path,
                    )
                )
                self.db.flush()
                draft_asset = DraftAsset(
                    draft_id=draft.id,
                    asset_type="image",
                    url=image_url,
                    local_path=local_name or "",
                    sort_order=sort_index + img_index,
                )
                self.db.add(draft_asset)
                self.db.flush()
                assets.append(_serialize_draft_asset(draft_asset))
                iteration_history.extend(image_result.get("iteration_history") or [])
                quality_check = image_result.get("quality_check") or {}

        return {
            "draft": _serialize_draft(draft),
            "assets": assets,
            "status": "partial" if errors else "completed",
            "errors": errors,
            "cover_strategy": draft_data.get("cover_strategy") or {},
            "image_prompt_spec": draft_data.get("image_prompt_spec") or {},
            "publish_tips": draft_data.get("publish_tips") or "",
            "final_image_prompt": final_image_prompt,
            "iteration_history": iteration_history,
            "quality_check": quality_check,
        }
