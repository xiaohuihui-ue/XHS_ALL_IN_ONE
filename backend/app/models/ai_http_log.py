from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
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
    # JSON 请求体（api_key 已脱敏为 ***）
    request_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # HTTP 响应状态码
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # JSON 响应体（text 类型截断 content 字段到 2000 字符）
    response_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 请求耗时，毫秒
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 错误信息
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
