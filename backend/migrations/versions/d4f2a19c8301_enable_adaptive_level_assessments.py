"""enable adaptive level assessments

Revision ID: d4f2a19c8301
Revises: b7e2c4a1f901
Create Date: 2026-09-18 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4f2a19c8301"
down_revision = "b7e2c4a1f901"
branch_labels = None
depends_on = None


def upgrade():
    assessment = sa.table(
        "assessment",
        sa.column("assessment_type", sa.String()),
        sa.column("is_adaptive", sa.Boolean()),
    )
    op.execute(
        assessment.update()
        .where(assessment.c.assessment_type == "level")
        .values(is_adaptive=True)
    )


def downgrade():
    assessment = sa.table(
        "assessment",
        sa.column("assessment_type", sa.String()),
        sa.column("is_adaptive", sa.Boolean()),
    )
    op.execute(
        assessment.update()
        .where(assessment.c.assessment_type == "level")
        .values(is_adaptive=False)
    )
