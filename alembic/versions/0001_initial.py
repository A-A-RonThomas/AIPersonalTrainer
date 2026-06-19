"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "program_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal", sa.String(20), nullable=False),
        sa.Column("training_days_per_week", sa.Integer(), nullable=False),
        sa.Column("current_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_cold_start", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "weekly_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("goal", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'draft'"),
        sa.Column("plan_json", JSONB(), nullable=False),
        sa.Column("trainer_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("approved_at", sa.DateTime()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("weekly_plans.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "exercise_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_template_id", sa.String(100), nullable=False),
        sa.Column("exercise_name", sa.String(200), nullable=False),
        sa.Column("slot", sa.String(100), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("sets_data", JSONB(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("hevy_workout_id", sa.String(100)),
    )

    op.create_index("ix_exercise_history_template_week", "exercise_history",
                    ["exercise_template_id", "week_number"])


def downgrade() -> None:
    op.drop_table("exercise_history")
    op.drop_table("chat_messages")
    op.drop_table("weekly_plans")
    op.drop_table("program_state")
