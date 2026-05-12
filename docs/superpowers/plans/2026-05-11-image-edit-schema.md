# Image Edit Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `backend/app/schemas/image_edit.py` with complete Pydantic v2 models for the image-to-image generation pipeline — zero changes to existing code.

**Architecture:** Five-layer schema: `ImageEditSpec` (structured input) → `EditPlan` (auditable intermediate) → `CompiledPrompmpiled prompts) → `GenerationResult` (raw output) → `QualityReport` (quality checks), all aggregated in `ImageGenerationArtifact` with lifecycle status and provenance metadata.

**Tech Stack:** Python 3.10+, Pydantic v2 (`pydantic.BaseModel`, `pydantic.Field`), standard library `enum`, `datetime`, `typing`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/app/schemas/image_edit.py` | All enums, models, and `HOME_DECOR_CHECK_NAMES` constant |
| Create | `tests/backend/test_image_edit_schema.py` | Pytest unit tests for schema validation |

No existing files are modified.

---

### Task 1: Enums

**Files:**
- Create: `backend/app/schemas/image_edit.py`
- Create: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backend/test_image_edit_schema.py
import pytest
from backend.app.schemas.image_edit import (
    TaskType,
    Domain,
    OutputGoal,
    RealismLevel,
    ArtifactStatus,
    CheckStatus,
)


def test_task_type_values():
    assert TaskType.style_transfer == "style_transfer"
    assert TaskType.room_makeover == "room_makeover"
    assert TaskType.material_replace == "material_replace"
    assert TaskType.lighting_enhance == "lighting_enhance"
    assert TaskType.declutter == "declutter"
    assert TaskType.cover_composition == "cover_composition"
    assert TaskType.detail_enhance == "detail_enhance"
    assert TaskType.variation == "variation"


def test_domain_values():
    assertcover"
    assert OutputGoal.xhs_body == "xhs_body"
    assert OutputGoal.general == "general"


def test_realism_level_values():
    assert RealismLevel.low == "low"
    assert RealismLevel.medium == "medium"
    assert RealismLevel.high == "high"


def test_artifact_status_values():
   tifactStatus.pending == "pending"
    assert ArtifactStatus.planning == "planning"
    assert ArtifactStatus.generating == "generating"
    assert ArtifactStatus.reviewing == "reviewing"
    assert ArtifactStatus.completed == "completed"
    assert ArtifactStatus.failed == "failed"


def test_check_status_values():
    assert CheckStatus.pass_ == "pass"
    assert CheckStatus.warning == "warning"
    assert CheckStatus.fail == "fail"
    assert CheckStatus.skipped == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd F:/Gitee/XHS_ALL_IN_ONE
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.app.schemas.image_edit'`

- [ ] **Step 3: Write minimal implementation — enums only**

```python
# backend/app/schemas/image_edit.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Fiels TaskType(str, Enum):
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add image_edit schema enums (TaskType, Domain, OutputGoal, RealismLevel, ArtifactStatus, CheckStatus)"
```

---

### Task 2: Layer 1 — ImageEditSpec

**Files:**
- Modify: `backend/app/schemas/image_edit.py` (append models)
- Modify: `tests/backend/test_image_edit_schema.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
from backend.app.schemas.image_edit import SourceImage, ImageEditSpec


def test_source_image_required_fields():
    img = SourceImage(id="img1", role="reference_room", url="https://example.com/a.jpg")
    assert img.id == "img1"
    assert img.role == "reference_room"
    assert img.url == "https://example.com/a.jpg"


def test_image_edit_spec_defaults():
    spec = ImageEditSpec(
        source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
        task_type=TaskType.style_transfer,
        edit_intent="Apply Japandi style",
    )
    assert spec.domain == Domain.general
    assert spec.preserve == []
    assert spec.change == []
    assert spec.avoid == []
    assert spec.output_goal == OutputGoal.general
    assert spec.realism_level == RealismLevel.high
    assert spec.room_type is None
    assert spec.decor_style is None


def test_image_edit_spec_full():
    spec = ImageEditSpec(
        soeImage(id="i1", role="ref", url="https://x.com/a.jpg")],
        task_type=TaskType.room_makeover,
        domain=Domain.home_decor,
        edit_intent="Transform to modern minimalist",
        preserve=["window position", "ceiling height"],
        change=["furniture", "wall color"],
        avoid=["clutter", "dark tones"],
        output_goal=OutputGoal.xhs_cover,
        realism_level=RealismLevel.high,
        room_type="living_room",
        decor_style="modern_minimalist",
    )
    assert spec.domain == Domain.home_decor
    assert len(spec.preserve) == 2
    assert spec.room_type == "living_room"


def test_image_edit_spec_edit_intent_min_length():
    with pytest.raises(Exception):
        ImageEditSpec(
            source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
            task_type=TaskType.variation,
            edit_intent="",
        )


def test_image_edit_spec_edit_intent_max_length():
    with pytest.raises(Exception):
        ImageEditSpec(
            source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
            task_type=TaskType.variation,
            edit_intent="x" * 501,
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_source_image_required_fields -v
```

Expected: `ImportError` — `SourceImage` not defined yet

- [ ] **Step 3: Implement Layer 1 models**

Append to `backend/app/schemas/image_edit.py` (after the enums):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS (including the 6 from Task 1)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add SourceImage and ImageEditSpec (Layer 1)"
```

---

### Task 3: Layer 2 — EditPlan

**Files:**
- Modify: `backend/app/schemas/image_edit.py`
- Modify: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
from backend.app.schemas.image_edit import EditStep, EditPlan


def test_edit_step_fields():
    step = EditStep(step=1, name="Analyze structure", instruction="Identify load-bearing walls and window positions")
    assert step.step == 1
    assert step.name == "Analyze structure"
    assert step.instruction == "Identify load-bearing walls and window positions"


def test_edit_plan_fields():
    plan = EditPlan(
        layout_policy="Preserve original spatial layout",
        style_policy="Apply Japandi aesthetic",
        material_policy="Use natural wood and linen textures",
        lighting_policy="Maintain natural light direction",
        composition_policy="Keep rule-of-thirds framing",
        steps=[
            EditStep(step=1, name="Analyze", instruction="Identify key structural elements"),
            EditStep(step=2, name="Style transfer", instruction="Apply target style to surfaces"),
        ],
    )
    assert plan.layout_policy == "Preserve original spatial layout"
    assert len(plan.steps) == 2
    assert plan.steps[0].step == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_edit_step_fields -v
```

Expected: `ImportError` — `EditStep` not defined yet

- [ ] **Step 3: Implement Layer 2 models**

Append to `backend/app/schemas/image_edit.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add EditStep and EditPlan (Layer 2)"
```

---

### Task 4: Layer 3 — CompiledPrompts

**Files:**
- Modify: `backend/app/schemas/image_edit.py`
- Modify: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
from backend.app.schemas.image_edit import CompiledPrompts


def test_compiled_prompts_defaults():
    cp = CompiledPrompts(
        positive_prompt="Japandi living room, natural wood, linen sofa",
        negative_prompt="clutter, dark tones, neon lights",
    )
    assert cp.positive_prompt == "Japandi living room, natural wood, linen sofa"
    assert cp.negative_prompt == "clutter, dark tones, neon lights"
    assert cp.compiler_version == "image_prompt_compiler_v1"


def test_compiled_prompts_custom_version():
    cp = CompiledPrompts(
        positive_prompt="modern kitchen",
        negative_prompt="old appliances",
        compiler_version="image_prompt_compiler_v2",
    )
    assert cp.compiler_version == "image_prompt_compiler_v2"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_compiled_prompts_defaults -v
```

Expected: `ImportError` — `CompiledPrompts` not defined yet

- [ ] **Step 3: Implement Layer 3 model**

Append to `backend/app/schemas/image_edit.py`:

```python
class CompiledPrompts(BaseModel):
    positive_prompt negative_prompt: str
    compiler_version: str = "image_prompt_compiler_v1"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add CompiledPrompts (Layer 3)"
```

---

### Task 5: Layer 4 — GenerationResult

**Files:**
- Modify: `backend/app/schemas/image_edit.py`
- Modify: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
from backend.app.schemas.image_edit import ResultAsset, GenerationResult


def test_result_asset_optional_dimensions():
    asset = ResultAsset(url="https://cdn.example.com/result.jpg")
    assert asset.url == "https://cdn.example.com/result.jpg"
    assert as is None
    assert asset.height is None


def test_result_asset_with_dimensions():
    asset = ResultAsset(url="https://cdn.example.com/result.jpg", width=1024, height=768)
    assert asset.width == 1024
    assert asset.height == 768


def test_generation_result_minimal():
    result = GenerationResult(assets=[ResultAsset(url="https://cdn.example.com/r.jpg")])
    assert len(result.assets) == 1
    assert result.raw_response is None


def test_generatiesult_with_raw():
    result = GenerationResult(
        assets=[ResultAsset(url="https://cdn.example.com/r.jpg", widtght=512)],
        raw_response={"model": "flux-dev", "seed": 42},
    )
    assert result.raw_response == {"model": "flux-dev", "seed": 42}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_result_asset_optional_dimensions -v
```

Expected: `ImportError` — `ResultAsset` not defined yet

- [ ] **Step 3: Implement Layer 4 models**

Append to `backend/app/schemas/image_edit.py`:

```python
class ResultAsset(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


class GenerationResult(BaseModel):
    assets: list[ResultAsset]
    raw_response: dict[str, Any] | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add ResultAsset and GenerationResult (Layer 4)"
```

---

### Task 6: Layer 5 — QualityReport + HOME_DECOR_CHECK_NAMES

**Files:**
- Modify: `backend/app/schemas/image_edit.py`
- Modify: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
from backend.app.schemas.image_edit import (
    QualityCheckItem,
    QualityReport,
    HOME_DECOR_CHECK_NAMES,
)


def test_quality_check_item_fields():
    item = QualityCheckItem(
        name="structure_preserved",
        status=CheckStatus.pass_,
        message="Original spatial layout retained",
    )
    assert item.name == "structure_preserved"
    assert item.status == CheckStatus.pass_
    assert item.message == "Original spatial layout retained"


def test_quality_report_passed():
    report = QualityReport(
        passed=True,
        checks=[
            QualityCheckItem(name="style_applied", status=CheckStatus.pass_, message="OK"),
        ],
    )
    assert report.passed is True
    assert len(report.checks) == 1


def test_quality_report_failed():
    report = QualityReport(
        passed=False,
        checks=[
            QualityCheckItem(name="material_realism", status=CheckStatus.fail, message="Textures look artificial"),
            QualityCheckItem(name="lighting_consistency", status=CheckStatus.warning, message="Minor shadow inconsistency"),
        ],
    )
    assert report.passed is False
    assert report.checks[0].status == CheckStatus.fail


def test_home_decor_check_names_is_tuple():
    assert isinstance(HOME_DECOR_CHECK_NAMES, tuple)


def test_home_decor_check_names_contains_required_checks():
    required = {
        "structure_preserved",
        "style_applied",
        "material_realism",
        "lighting_consistency",
        "furniture_geometry",
        "home_decor_expressiveness",
        "xhs_cover_readiness",
    }
    assert required == set(HOME_DECOR_CHECK_NAMES)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_quality_check_item_fields -v
```

Expected: `ImportError` — `QualityCheckItem` not defined yet

- [ ] **Step 3: Implement Layer 5 models and constant**

Append to `backend/app/schemas/image_edit.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add QualityCheckItem, QualityReport, HOME_DECOR_CHECK_NAMES (Layer 5)"
```

---

### Task 7: Top-level — Provenance + ImageGenerationArtifact

**Files:**
- Modify: `backend/app/schemas/image_edit.py`
- Modify: `tests/backend/test_image_edit_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_image_edit_schema.py`:

```python
fr datetime import datetime, timezone
from backend.app.schemas.image_edit import Provenance, ImageGenerationArtifact


def test_provenance_defaults():
    now = datetime.now(timezone.utc)
    prov = Provenance(created_at=now)
    assert prov.created_at == now
    assert prov.model_config_id is None
    assert prov.model_name is None
    assert prov.knowledge_base is None
    assert prov.prompt_compiler == "image_prompt_compiler_v1"


def test_provenance_full():
    now = datetime.now(timezone.utc)
    prov = Provenance(
        model_config_id=42,
        model_name="flux-dev",
        created_at=now,
        knowledge_base="home_decor_v1",
        prompt_compiler="image_prompt_compiler_v2",
    )
    assert prov.model_config_id == 42
    assert prov.model_name == "flux-dev"
    assert prov.knowledge_base == "home_decor_v1"


def test_artifact_pending_state():
    now = datetime.now(timezone.utc)
    artifact = ImageGenerationArtifact(
        request_id="550e8400-e29b-41d4-a716-446655440000",
        status=ArtifactStatus.pending,
        source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
        provenance=Provenance(created_at=now),
    )
    assert artifact.status == ArtifactStatus.pending
    assert artifact.normalized_spec is None
    assert artifact.edit_plan is None
    assert artifact.compiled_prompts is None
    assert artifact.result_assets == []
    assert artifact.quality_report is None
    assert artifact.errors == []


def test_artifact_completed_state():
    now = datetime.now(timezone.utc)
    src = SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")
    spec = ImageEditSpec(
        source_images=[src],
        task_type=TaskType.style_transfer,
        edit_intent="Apply Japandi style",
    )
    plan = EditPlan(
        layout_policy="Preserve layout",
        style_policy="Japandi",
        material_policy="Natural materials",
        lighting_policy="Soft natural light",
        composition_policy="Rule of thirds",
        steps=[EditStep(step=1, name="Transfer", instruction="Apply style")],
    )
    prompts = CompiledPrompts(
        positive_prompt="Japandi room",
        negative_prompt="clutter",
    )
    report = QualityReport(
        passed=True,
        checks=[QualityCheckItem(name="style_applied", status=CheckStatus.pass_, message="OK")],
    )
    artifact = ImageGenerationArtifact(
        request_id="550e8400-e29b-41d4-a716-446655440001",
        status=ArtifactStatus.completed,
        source_images=[src],
        normalized_spec=spec,
        edit_plan=plan,
        compiled_prompts=prompts,
        result_assets=[ResultAsset(url="https://cdn.example.com/out.jpg", width=1024, height=1024)],
        quality_report=report,
        provenance=Provenance(model_name="flux-dev", created_at=now),
    )
    assert artifact.status == ArtifactStatus.completed
    assert artifact.normalized_spec is not None
    assert artifact.edit_plan is not None
    assert artifact.compiled_prompts is not None
    assert len(artifact.result_assets) == 1
    assert artifact.quality_report.passed is True


def test_artifact_failed_state():
    now = me.now(timezone.utc)
    artifact = ImageGenerationArtifact(
        request_id="550e8400-e29b-41d4-a716-446655440002",
        status=ArtifactStatus.failed,
        source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
        provenance=Provenance(created_at=now),
        errors=["Model timeout after 30s", "Retry limit exceeded"],
    )
    assert artifact.status == ArtifactStatus.failed
    assert len(artifact.errors) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/backend/test_image_edit_schema.py::test_provenance_defaults -v
```

Expected: `ImportError` — `Provenance` not defined yet

- [ ] **Step 3: Implement Provenance and ImageGenerationArtifact**

Append to `backend/app/schemas/image_edit.py`:

```python
class Provenance(BaseModel):
    model_config_id: int | None = None
    model_name: str | None = None
    created_at: datetime
    knowledge_base: str | None = None
    prompt_compiler: str = "image_prompt_compn

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
    errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run the full test suite to verify everything passes**

```bash
python -m pytest tests/backend/test_image_edit_schema.py -v
```

Expected: all tests PASS (should be ~25 tests total)

- [ ] **Step 5: Also verify existing tests are unaffected**

```bash
python -m pytest tests/backend/test_api.py -v
```

Expected: same results as before this feature (no regressions)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/image_edit.py tests/backend/test_image_edit_schema.py
git commit -m "feat: add Provenance and ImageGenerationArtifact (top-level artifact)"
```

---

## Final State

After all tasks complete, `backend/app/schemas/image_edit.py` will contain (in order):

1. Imports: `from __future__ import annotations`, `datetime`, `enum`, `typing.Any`, `pydantic`
2. Enums: `TaskType`, `Domain`, `OutputGoal`, `RealismLevel`, `ArtifactStatus`, `CheckStatus`
3. Layer 1: `SourceImage`, `ImageEditSpec`
4. Layer 2: `EditStep`, `EditPlan`
5. Layer 3: `CompiledPrompts`
6. Layer 4: `ResultAsset`, `GenerationResult`
7. Layer 5: `QualityCheckItem`, `QualityReport`, `HOME_DECOR_CHECK_NAMES`
8. Top-level: `Provenance`, `ImageGenerationArtifact`

No existing files are modified. The old `POST /ai/images/generate` endpoint is untouched.
