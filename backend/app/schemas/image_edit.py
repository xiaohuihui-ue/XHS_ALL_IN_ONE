from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    style_transfer    = "style_transfer"
    room_makeover     = "room_makeover"
    material_replace  = "material_replace"
    lighting_enhance  = "lighting_enhance"
    declutter         = "declutter"
    cover_composition = "cover_composition"
    detail_enhance    = "detail_enhance"
    variation         = "variation"


class Domain(str, Enum):
    home_decor = "home_decor"
    general    = "general"


class OutputGoal(str, Enum):
    xhs_cover = "xhs_cover"
    xhs_body  = "xhs_body"
    general   = "general"


class RealismLevel(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class ArtifactStatus(str, Enum):
    pending    = "pending"
    planning   = "planning"
    generating = "generating"
    reviewing  = "reviewing"
    completed  = "completed"
    failed     = "failed"


class CheckStatus(str, Enum):
    pass_   = "pass"
    warning = "warning"
    fail    = "fail"
    skipped = "skipped"


class SourceImage(BaseModel):
    id: str
    role: str
    url: str


class ImageEditSpec(BaseModel):
    source_images: list[SourceImage]
    task_type: TaskType
    domain: Domain = Domain.general
    edit_intent: str = Field(min_length=1, max_length=500)
    preserve: list[str] = Field(default_factory=list)
    change: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    output_goal: OutputGoal = OutputGoal.general
    realism_level: RealismLevel = RealismLevel.high
    room_type: str | None = None
    decor_style: str | None = None
