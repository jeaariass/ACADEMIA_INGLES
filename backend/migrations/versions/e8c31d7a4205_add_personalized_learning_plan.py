"""add personalized learning plan

Revision ID: e8c31d7a4205
Revises: d4f2a19c8301
Create Date: 2026-09-18 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e8c31d7a4205"
down_revision = "d4f2a19c8301"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_topic_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_attempt_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("evidence_correct", sa.Integer(), nullable=False),
        sa.Column("evidence_total", sa.Integer(), nullable=False),
        sa.Column("evidence_percentage", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["diagnostic_attempt_id"], ["assessment_attempt.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_user_topic_plan_user_topic"),
    )


def downgrade():
    op.drop_table("user_topic_plan")
