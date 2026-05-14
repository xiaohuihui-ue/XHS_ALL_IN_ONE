"""add ai_http_logs table

Revision ID: 648c0a4a687f
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14 15:05:41.301808
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '648c0a4a687f'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_http_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=True),
    sa.Column('request_type', sa.String(length=16), nullable=False),
    sa.Column('method', sa.String(length=8), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('request_body', sa.JSON(), nullable=True),
    sa.Column('response_status', sa.Integer(), nullable=True),
    sa.Column('response_body', sa.JSON(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ai_http_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_http_logs_task_id'), ['task_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ai_http_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_http_logs_task_id'))

    op.drop_table('ai_http_logs')
