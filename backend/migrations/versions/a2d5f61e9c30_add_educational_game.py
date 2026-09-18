"""add educational game

Revision ID: a2d5f61e9c30
Revises: f4b8c21d7a10
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa


revision = "a2d5f61e9c30"
down_revision = "f4b8c21d7a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "game_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("difficulty_tier", sa.Integer(), nullable=False),
        sa.Column("completion_number", sa.Integer(), nullable=False),
        sa.Column("target_distance", sa.Integer(), nullable=False),
        sa.Column("target_difficulty", sa.Integer(), nullable=False),
        sa.Column("level_code", sa.String(length=10), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False),
        sa.Column("energy_end", sa.Float(), nullable=False),
        sa.Column("questions_answered", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_game_run_user_status",
        "game_run",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "game_challenge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_run_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("saved_vocabulary_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_label", sa.String(length=220), nullable=False),
        sa.Column("skill", sa.String(length=30), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("option_a", sa.String(length=500), nullable=False),
        sa.Column("option_b", sa.String(length=500), nullable=False),
        sa.Column("option_c", sa.String(length=500), nullable=False),
        sa.Column("option_d", sa.String(length=500), nullable=False),
        sa.Column("correct_option", sa.String(length=1), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("selected_option", sa.String(length=1), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_run_id"], ["game_run.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["saved_vocabulary_id"], ["saved_vocabulary.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_game_challenge_run",
        "game_challenge",
        ["game_run_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_game_challenge_run", table_name="game_challenge")
    op.drop_table("game_challenge")
    op.drop_index("ix_game_run_user_status", table_name="game_run")
    op.drop_table("game_run")
