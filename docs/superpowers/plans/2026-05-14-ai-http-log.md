# AI HTTP 请求日志记录实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `ai_service.py` 中所有 AI 服务 HTTP 请求（文本生成 + 图片生成）自动记录到数据库，包含任务 ID、请求类型（text/image）、请求体、响应体、耗时。

**Architecture:**
- 新建 `AiHttpLog` 模型（独立于通用 `ApiLog`），字段针对 AI 请求优化
- 通过 Python `contextvars` 在请求链路中传递 `task_id`，调用方无需显式透传
- 提供 `ai_http_log()` 上下文管理器，封装 `requests.post`，自动记录前后数据
- 在 `ai_service.py` 所有 HTTP 调用处用 `with ai_http_log()` 包装

**Tech Stack:** SQLAlchemy, contextvars, requests, Alembic

---

## 文件变更总览

| 操作 | 文件 |
|------|------|
| 新建 | `backend/app/models/ai_http_log.py` |
| 修改 | `backend/app/models/__init__.py` |
| 新建 | `backend/alembic/versions/<hash>_add_ai_http_logs_table.py` |
| 新建 | `backend/app/services/http_logging.py` |
| 修改 | `backend/app/services/ai_service.py` |
| 新建 | `tests/backend/test_ai_http_log.py` |

---

## Task 1: 新建 `AiHttpLog` 模型

**Files:**
- Create: `backend/app/models/ai_http_log.py`

- [ ] **Step 1: 写入模型文件**

```python
# backend/app/models/ai_http_log.py
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class RequestType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class AiHttpLog(Base):
    __tablename__ = "ai_http_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 关联 tasks.id，nullable（某些直接调用可能无 task 上下文）
    task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # 请求类型：text=文本生成，image=图片生成
    request_type: Mapped[str] = mapped_column(String(16))
    # HTTP 方法，固定 POST
    method: Mapped[str] = mapped_column(String(8), default="POST")
    # 完整请求 URL
    url: Mapped[str] = mapped_column(Text)
    # JSON 请求体（完整，敏感信息如 api_key 已脱敏）
    request_body: Mapped[Optional[dict]] = mapped_column(default=None)
    # HTTP 响应状态码
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # JSON 响应体（text 类型截断 content 字段到 2000 字符，image 类型保留 url）
    response_body: Mapped[Optional[dict]] = mapped_column(default=None)
    # 请求耗时，毫秒
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 错误信息
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
```

- [ ] **Step 2: 导出到 `__init__.py`**

修改 `backend/app/models/__init__.py`，在 import 区末尾添加：

```python
from backend.app.models.ai_http_log import AiHttpLog, RequestType
```

并在 `__all__` 列表中加入 `"AiHttpLog"` 和 `"RequestType"`。

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/ai_http_log.py backend/app/models/__init__.py
git commit -m "feat(model): add AiHttpLog model for AI HTTP request logging"
```

---

## Task 2: 创建 Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/<hash>_add_ai_http_logs_table.py`
- Verify: `backend/alembic/versions/fc35ffa0c18b_add_monitoring_crawl_fields.py` (确认 parent revision)

- [ ] **Step 1: 查看当前最新 migration 确定 parent**

```bash
grep "Revises:" backend/alembic/versions/fc35ffa0c18b_add_monitoring_crawl_fields.py
```
Expected 输出: `Revises: b7626fb8d48a`

- [ ] **Step 2: 生成 migration 文件**

```bash
cd F:/Gitee/XHS_ALL_IN_ONE && python -m alembic revision --autogenerate -m "add ai_http_logs table"
```

- [ ] **Step 3: 检查生成的 migration 文件内容**

文件应包含创建 `ai_http_logs` 表，包含字段：
`id`, `task_id`, `request_type`, `method`, `url`, `request_body`, `response_status`, `response_body`, `duration_ms`, `error`, `created_at`

- [ ] **Step 4: 如 migration 文件不完整，手动补充**

如果 autogenerate 遗漏字段，手动编辑生成的 migration 文件。

- [ ] **Step 5: 运行 migration 验证**

```bash
cd F:/Gitee/XHS_ALL_IN_ONE && python -c "from backend.app.core.database import init_db; init_db()"
```

- [ ] **Step 6: 提交**

```bash
git add backend/alembic/versions/
git commit -m "feat(migration): add ai_http_logs table for AI HTTP request logging"
```

---

## Task 3: 编写 `http_logging.py` 日志工具

**Files:**
- Create: `backend/app/services/http_logging.py`

- [ ] **Step 1: 写入工具文件**

```python
# backend/app/services/http_logging.py
from __future__ import annotations

import json
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
    """将 text 响应中的 content 字段截断"""
    if not body:
        return body
    truncated = dict(body)
    try:
        choices = truncated.get("choices", [])
        for choice in choices:
            msg = choice.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > MAX_TEXT_CONTENT_LENGTH:
                msg["content"] = content[:MAX_TEXT_CONTENT_LENGTH] + f"... [truncated {len(content) - MAX_TEXT_CONTENT_LENGTH} chars]"
    except Exception:
        pass
    return truncated


def ai_http_log(
    *,
    task_id: Optional[int],
    request_type: RequestType,
    url: str,
    request_body: dict,
) -> requests.Response:
    """
    包装 requests.post，自动记录请求/响应到 ai_http_logs 表。
    用法：
        with ai_http_log(task_id=ctx_task_id, request_type=RequestType.TEXT, url=url, request_body=body) as resp:
            # resp 是 requests.Response，可正常调用 .json() 等方法
            pass
    """
    # 尝试从上下文变量获取 task_id（覆盖参数传入的值）
    effective_task_id = _current_task_id.get() if _current_task_id.get() is not None else task_id
    masked_body = _mask_api_key(request_body)
    start_ms = time.time()
    log_record: dict[str, Any] = {
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

    class _LoggedResponse:
        def __init__(self, raw: requests.Response, request_type: str):
            self._raw = raw
            self._request_type = request_type

        def json(self) -> dict:
            return self._raw.json()

        def raise_for_status(self) -> None:
            self._raw.raise_for_status()

        @property
        def status_code(self) -> int:
            return self._raw.status_code

        @property
        def content(self) -> bytes:
            return self._raw.content

        @property
        def text(self) -> str:
            return self._raw.text

        def _finalize(self, exc: Optional[Exception] = None) -> None:
            duration_ms = int((time.time() - start_ms) * 1000)
            log_record["duration_ms"] = duration_ms
            if exc is not None:
                log_record["error"] = str(exc)
            else:
                log_record["response_status"] = self._raw.status_code
                try:
                    raw_json = self._raw.json()
                    if self._request_type == RequestType.TEXT.value:
                        log_record["response_body"] = _truncate_text_response(raw_json)
                    else:
                        log_record["response_body"] = raw_json
                except Exception:
                    log_record["response_body"] = {"_raw_text": self._raw.text[:500]}
            # 写入数据库
            try:
                from backend.app.core.database import SessionLocal
                db = SessionLocal()
                try:
                    db.add(AiHttpLog(**log_record))
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()
            except Exception:
                # 记录失败不应影响主流程
                pass

    raw_resp: requests.Response | None = None
    exc: Exception | None = None
    try:
        raw_resp = requests.post(
            url,
            headers=request_body.get("headers", {}) if "headers" in request_body else {"Content-Type": "application/json"},
            json=request_body,
            timeout=request_body.pop("_timeout", 60),
        )
    except Exception as e:
        exc = e
        raw_resp = None

    logged = _LoggedResponse(raw_resp, log_record["request_type"]) if raw_resp else _LoggedResponse(None, log_record["request_type"])
    logged._finalize(exc)
    if exc:
        raise exc
    return logged
```

> **注：** `requests.post` 的 headers 不要放在 `request_body` 中传入，上面代码将 `headers` 和 `_timeout` 作为特殊 key 处理。

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/http_logging.py
git commit -m "feat(service): add ai_http_log context manager for HTTP request logging"
```

---

## Task 4: 在 `ai_service.py` 中集成日志记录

**Files:**
- Modify: `backend/app/services/ai_service.py`

- [ ] **Step 1: 在文件顶部添加 import**

在 `ai_service.py` 第 7 行后（`import requests` 之后）添加：

```python
from backend.app.services.http_logging import ai_http_log, set_current_task_id
```

- [ ] **Step 2: 给 `AiService` 添加 `task_id` 支持**

在 `AiService` 类的 `__init__` 中添加 `task_id` 参数：

```python
def __init__(self, task_id: int | None = None) -> None:
    self.task_id = task_id
    if task_id is not None:
        set_current_task_id(task_id)
```

- [ ] **Step 3: 创建 HTTP 调用的 body builder helper**

在 `ai_service.py` 文件中 `OpenAICompatibleTextClient` 类之前添加：

```python
def _build_chat_body(model_config, api_key, messages, temperature=0.7, extra=None):
    body = {
        "model": model_config.model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if extra:
        body.update(extra)
    return body
```

- [ ] **Step 4: 修改 `OpenAICompatibleTextClient._complete()`**

找到 `ai_service.py` 第 251 行附近的 `requests.post` 调用，替换为：

```python
        # 原来：
        # response = requests.post(endpoint, headers={...}, json={...}, timeout=60)

        # 改为：
        body = {
            "model": model_config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        _headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        logged_resp = ai_http_log(
            task_id=None,
            request_type="text",
            url=endpoint,
            request_body={"headers": _headers, **body, "_timeout": 60},
        )
        response = MagicMock()
        response.status_code = logged_resp.status_code
        response.json = logged_resp.json
        response.raise_for_status = logged_resp.raise_for_status
```

> **注意：** 需要在文件顶部添加 `from unittest.mock import MagicMock`（如果没有的话）。

- [ ] **Step 5: 逐个修改其余 7 处 `requests.post` 调用**

每处调用的替换模式相同：将原始 `requests.post(...)` 替换为 `ai_http_log(...)` + 构建一个 MagicMock 响应对象。

涉及的方法（按文件行号顺序）：
1. 第 442 行附近：`generate_agent_drafts` 中的 `requests.post`
2. 第 693 行附近：`_generate_draft_prompt` 中的 `requests.post`
3. 第 736 行附近：`_score_draft_prompt` 中的 `requests.post`
4. 第 781 行附近：`_rewrite_draft_prompt` 中的 `requests.post`
5. 第 940 行附近：`generate_image` 中的 `requests.post` → `request_type="image"`
6. 第 1045 行附近：`describe_image` 中的 `requests.post`
7. 第 1118 行附近：`_check_generated_image_quality` 中的 `requests.post`

> **提示：** 每处 `ai_http_log` 调用时，`request_type` 参数只有第 5 处传 `"image"`，其余都传 `"text"`。`timeout` 通过 body 中的 `"_timeout"` key 传入。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/ai_service.py
git commit -m "feat(ai-service): integrate http logging into all AI API calls"
```

---

## Task 5: 编写测试

**Files:**
- Create: `tests/backend/test_ai_http_log.py`

- [ ] **Step 1: 写入测试文件**

```python
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# 设置临时数据库
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


def test_ai_http_log_records_success(tmp_path):
    from backend.app.services.http_logging import ai_http_log, _mask_api_key, _truncate_text_response

    # _mask_api_key
    body = {"api_key": "sk-secret", "model": "gpt-4"}
    masked = _mask_api_key(body)
    assert masked["api_key"] == "***"
    assert masked["model"] == "gpt-4"

    # _truncate_text_response
    long_content = "x" * 3000
    resp = {
        "choices": [{"message": {"content": long_content}}],
        "usage": {"total_tokens": 100},
    }
    truncated = _truncate_text_response(resp)
    content = truncated["choices"][0]["message"]["content"]
    assert "[truncated" in content
    assert len(content) < 3000


def test_ai_http_log_request_type_text(tmp_path):
    from backend.app.services.http_logging import ai_http_log

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        with patch("backend.app.services.http_logging.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db

            body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
            resp = ai_http_log(task_id=42, request_type="text", url="http://example.com/chat", request_body=body)

            assert resp.status_code == 200
            mock_db.add.assert_called_once()
            call_kwargs = mock_db.add.call_args[0][0]
            assert call_kwargs["task_id"] == 42
            assert call_kwargs["request_type"] == "text"
            assert call_kwargs["url"] == "http://example.com/chat"
            assert call_kwargs["response_status"] == 200


def test_ai_http_log_request_type_image(tmp_path):
    from backend.app.services.http_logging import ai_http_log

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"url": "http://img.example.com/1.jpg"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        with patch("backend.app.services.http_logging.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db

            body = {"model": "dall-e-3", "prompt": "a cat"}
            resp = ai_http_log(task_id=99, request_type="image", url="http://example.com/images", request_body=body)

            call_kwargs = mock_db.add.call_args[0][0]
            assert call_kwargs["task_id"] == 99
            assert call_kwargs["request_type"] == "image"


def test_ai_http_log_error_preserved(tmp_path):
    from backend.app.services.http_logging import ai_http_log

    with patch("requests.post", side_effect=Exception("connection timeout")):
        with patch("backend.app.services.http_logging.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db

            body = {"model": "gpt-4"}
            with pytest.raises(Exception, match="connection timeout"):
                ai_http_log(task_id=1, request_type="text", url="http://example.com", request_body=body)

            call_kwargs = mock_db.add.call_args[0][0]
            assert call_kwargs["error"] == "connection timeout"
```

- [ ] **Step 2: 运行测试验证**

```bash
cd F:/Gitee/XHS_ALL_IN_ONE && pytest tests/backend/test_ai_http_log.py -v
```

Expected: 4 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/backend/test_ai_http_log.py
git commit -m "test: add unit tests for AI HTTP logging"
```

---

## Task 6: 端到端集成验证（可选）

验证 `api/ai.py` 中创建 `Task` 后，日志能正确关联 `task_id`。

- [ ] **Step 1: 检查 `AiService` 实例化位置**

在 `api/ai.py` 中搜索 `AiService(` 或 `TextAiClient(` 的使用位置，确认可以传入 `task_id`。

如果当前代码没有传递 `task_id`，在 `agent_drafts_chat_completions` 等函数中：
- 在 `db.commit()` 创建 `Task` 后
- 将 `AiService(task_id=task.id)` 传入依赖或直接使用

---

## 自检清单

- [ ] 每个 `requests.post` 都已替换为 `ai_http_log`
- [ ] `request_type="text"` / `"image"` 分类正确
- [ ] `api_key` 在 `request_body` 中已脱敏为 `"***"`
- [ ] text 响应 `content` 字段已截断到 2000 字符
- [ ] 数据库写入异常不会导致主流程崩溃
- [ ] 所有测试通过
