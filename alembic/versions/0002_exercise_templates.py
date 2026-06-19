"""add exercise_templates table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercise_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slot", sa.String(100), nullable=False),
        sa.Column("primary_muscle", sa.String(100)),
        sa.Column("secondary_muscles", JSONB(), nullable=False, server_default="'[]'"),
        sa.Column("category", sa.String(100)),
    )
    op.create_index("ix_exercise_templates_slot", "exercise_templates", ["slot"])


def downgrade() -> None:
    op.drop_table("exercise_templates")
