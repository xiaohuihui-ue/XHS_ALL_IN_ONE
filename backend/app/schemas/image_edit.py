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


# Layer 1

class SourceImage(BaseModel):
    id: str
    role: str
    url: str


class ImageEditSpec(BaseModel):
    source_images: list[SourceImage] = Field(min_length=1)
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


# Layer 2

class EditStep(BaseModel):
    step: int
    name: str
    instruction: str


class EditPlan(BaseModel):
    layout_policy: str
    style_policy: str
    material_policy: str
    lighting_policy: str
    composition_policy: str
    steps: list[EditStep]


# Layer 3

class CompiledPrompts(BaseModel):
    positive_prompt: str
    negative_prompt: str
    compiler_version: str = "image_prompt_compiler_v1"


# Layer 4

class ResultAsset(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


class GenerationResult(BaseModel):
    assets: list[ResultAsset]
    raw_response: dict[str, Any] | None = None


# Layer 5

class QualityCheckItem(BaseModel):
    name: str
    status: CheckStatus
    message: str


class QualityReport(BaseModel):
    passed: bool
    checks: list[QualityCheckItem]


HOME_DECOR_CHECK_NAMES: tuple[str, ...] = (
    "structure_preserved",
    "style_applied",
    "material_realism",
    "lighting_consistency",
    "furniture_geometry",
    "home_decor_expressiveness",
    "xhs_cover_readiness",
)


# Top-level

class Provenance(BaseModel):
    model_config_id: int | None = None
    model_name: str | None = None
    created_at: datetime
    knowledge_base: str | None = None
    prompt_compiler: str = "image_prompt_compiler_v1"


class ImageReport(BaseModel):
    file_name: str
    file_path: str
    download_url: str


class ImageGenerationArtifact(BaseModel):
    request_id: str
    status: ArtifactStatus
    source_images: list[SourceImage]
    normalized_spec: ImageEditSpec | None = None
    edit_plan: EditPlan | None = None
    compiled_prompts: CompiledPrompts | None = None
    result_assets: list[ResultAsset] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    provenance: Provenance
    report: ImageReport | None = None
    errors: list[str] = Field(default_factory=list)
