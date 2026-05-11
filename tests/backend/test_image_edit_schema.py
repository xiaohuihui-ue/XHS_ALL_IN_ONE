import pytest
from backend.app.schemas.image_edit import (
    TaskType,
    Domain,
    OutputGoal,
    RealismLevel,
    ArtifactStatus,
    CheckStatus,
    SourceImage,
    ImageEditSpec,
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
