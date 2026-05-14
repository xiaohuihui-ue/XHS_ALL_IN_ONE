from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any, Optional

import requests

from backend.app.models.ai_http_log import AiHttpLog, RequestType

# 线程/协程安全的上下文变量，用于传递当前 task_id
_current_task_id: ContextVar[Optional[int]] = ContextVar("current_task_id", default=None)

MAX_TEXT_CONTENT_LENGTH = 2000  # text 类型响应 content 截断长度


def get_current_task_id() -> Optional[int]:
    return _current_task_id.get()


def set_current_task_id(task_id: Optional[int]) -> Any:
    return _current_task_id.set(task_id)


def _mask_api_key(body: dict) -> dict:
    """将请求体中的 api_key 脱敏为 ***"""
    if not body:
        return body
    masked = dict(body)
    if "api_key" in masked:
        masked["api_key"] = "***"
    return masked


def _truncate_text_response(body: dict) -> dict:
    """将 text 响应中的 content 字段截断到 MAX_TEXT_CONTENT_LENGTH"""
    if not body:
        return body
    truncated = dict(body)
    try:
        choices = truncated.get("choices", [])
        for choice in choices:
            msg = choice.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > MAX_TEXT_CONTENT_LENGTH:
                msg["content"] = (
                    content[:MAX_TEXT_CONTENT_LENGTH]
                    + f"... [truncated {len(content) - MAX_TEXT_CONTENT_LENGTH} chars]"
                )
    except Exception:
        pass
    return truncated


class _LoggedResponse:
    """对 requests.Response 的代理，支持在结束后自动写入数据库"""

    def __init__(self, raw: Optional[requests.Response], request_type: str, log_record: dict[str, Any]):
        self._raw = raw
        self._request_type = request_type
        self._log_record = log_record

    @property
    def status_code(self) -> int:
        return self._raw.status_code if self._raw else 0

    def json(self) -> dict:
        return self._raw.json() if self._raw else {}

    def raise_for_status(self) -> None:
        if self._raw:
            self._raw.raise_for_status()

    @property
    def content(self) -> bytes:
        return self._raw.content if self._raw else b""

    @property
    def text(self) -> str:
        return self._raw.text if self._raw else ""

    def _finalize(self, exc: Optional[Exception]) -> None:
        self._log_record["duration_ms"] = int((time.time() - self._log_record.pop("_start_time")) * 1000)
        if exc is not None:
            self._log_record["error"] = str(exc)
        else:
            self._log_record["response_status"] = self.status_code
            try:
                raw_json = self._raw.json()
                if self._request_type == RequestType.TEXT.value:
                    self._log_record["response_body"] = _truncate_text_response(raw_json)
                else:
                    self._log_record["response_body"] = raw_json
            except Exception:
                self._log_record["response_body"] = {"_raw_text": self._raw.text[:500]} if self._raw else {}
        self._write_to_db()

    def _write_to_db(self) -> None:
        try:
            from backend.app.core.database import SessionLocal

            db = SessionLocal()
            try:
                db.add(AiHttpLog(**self._log_record))
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
        except Exception:
            pass  # 记录失败不应影响主流程


def ai_http_log(
    *,
    task_id: Optional[int],
    request_type: RequestType,
    url: str,
    request_body: dict,
) -> _LoggedResponse:
    """
    包装 requests.post，自动记录请求/响应到 ai_http_logs 表。

    用法：
        resp = ai_http_log(
            task_id=42,
            request_type=RequestType.TEXT,
            url="https://api.example.com/chat",
            request_body={"model": "gpt-4", "messages": [...], "_timeout": 60},
        )
        resp.raise_for_status()
        data = resp.json()
    """
    effective_task_id = _current_task_id.get() if _current_task_id.get() is not None else task_id
    masked_body = _mask_api_key(request_body)
    timeout = masked_body.pop("_timeout", 60)
    headers = masked_body.pop("_headers", {"Content-Type": "application/json"})

    log_record: dict[str, Any] = {
        "_start_time": time.time(),
        "task_id": effective_task_id,
        "request_type": request_type.value if isinstance(request_type, RequestType) else request_type,
        "method": "POST",
        "url": url,
        "request_body": masked_body,
        "response_status": None,
        "response_body": None,
        "duration_ms": None,
        "error": None,
    }

    raw_resp: Optional[requests.Response] = None
    exc: Optional[Exception] = None
    try:
        raw_resp = requests.post(url, headers=headers, json=masked_body, timeout=timeout)
    except Exception as e:
        exc = e

    logged = _LoggedResponse(raw_resp, log_record["request_type"], log_record)
    logged._finalize(exc)
    if exc:
        raise exc
    return logged
