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
