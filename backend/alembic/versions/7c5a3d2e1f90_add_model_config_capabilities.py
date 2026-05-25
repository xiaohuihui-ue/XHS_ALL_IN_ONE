"""add model config capabilities

Revision ID: 7c5a3d2e1f90
Revises: 648c0a4a687f
Create Date: 2026-05-17 11:15:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c5a3d2e1f90"
down_revision: Union[str, None] = "648c0a4a687f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_configs", sa.Column("capabilities", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE model_configs SET capabilities = '[\"text_generation\"]' "
        "WHERE model_type = 'text' AND capabilities IS NULL"
    )
    op.execute(
        "UPDATE model_configs SET capabilities = '[\"image_generation\", \"image_edit\"]' "
        "WHERE model_type = 'image' AND capabilities IS NULL"
    )


def downgrade() -> None:
    op.drop_column("model_configs", "capabilities")
