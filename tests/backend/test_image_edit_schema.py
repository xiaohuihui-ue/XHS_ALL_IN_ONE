import pytest
from datetime import datetime, timezone

from backend.app.schemas.image_edit import (
    TaskType,
    Domain,
    OutputGoal,
    RealismLevel,
    ArtifactStatus,
    CheckStatus,
    SourceImage,
    ImageEditSpec,
    EditStep,
    EditPlan,
    CompiledPrompts,
    ResultAsset,
    GenerationResult,
    QualityCheckItem,
    QualityReport,
    HOME_DECOR_CHECK_NAMES,
    Provenance,
    ImageGenerationArtifact,
)


# --- Enums ---

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
    assert Domain.home_decor == "home_decor"
    assert Domain.general == "general"


def test_output_goal_values():
    assert OutputGoal.xhs_cover == "xhs_cover"
    assert OutputGoal.xhs_body == "xhs_body"
    assert OutputGoal.general == "general"


def test_realism_level_values():
    assert RealismLevel.low == "low"
    assert RealismLevel.medium == "medium"
    assert RealismLevel.high == "high"


def test_artifact_status_values():
    assert ArtifactStatus.pending == "pending"
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


# --- Layer 1: SourceImage, ImageEditSpec ---

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
        source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
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


# --- Layer 2: EditStep, EditPlan ---

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


# --- Layer 3: CompiledPrompts ---

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


# --- Layer 4: ResultAsset, GenerationResult ---

def test_result_asset_optional_dimensions():
    asset = ResultAsset(url="https://cdn.example.com/result.jpg")
    assert asset.url == "https://cdn.example.com/result.jpg"
    assert asset.width is None
    assert asset.height is None


def test_result_asset_with_dimensions():
    asset = ResultAsset(url="https://cdn.example.com/result.jpg", width=1024, height=768)
    assert asset.width == 1024
    assert asset.height == 768


def test_generation_result_minimal():
    result = GenerationResult(assets=[ResultAsset(url="https://cdn.example.com/r.jpg")])
    assert len(result.assets) == 1
    assert result.raw_response is None


def test_generation_result_with_raw():
    result = GenerationResult(
        assets=[ResultAsset(url="https://cdn.example.com/r.jpg", width=512, height=512)],
        raw_response={"model": "flux-dev", "seed": 42},
    )
    assert result.raw_response == {"model": "flux-dev", "seed": 42}


# --- Layer 5: QualityReport, HOME_DECOR_CHECK_NAMES ---

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


# --- Top-level: Provenance, ImageGenerationArtifact ---

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
    now = datetime.now(timezone.utc)
    artifact = ImageGenerationArtifact(
        request_id="550e8400-e29b-41d4-a716-446655440002",
        status=ArtifactStatus.failed,
        source_images=[SourceImage(id="i1", role="ref", url="https://x.com/a.jpg")],
        provenance=Provenance(created_at=now),
        errors=["Model timeout after 30s", "Retry limit exceeded"],
    )
    assert artifact.status == ArtifactStatus.failed
    assert len(artifact.errors) == 2
