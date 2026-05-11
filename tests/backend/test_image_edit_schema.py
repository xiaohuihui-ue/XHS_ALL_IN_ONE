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
