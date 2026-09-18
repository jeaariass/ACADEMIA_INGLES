"""add CEFR-relative difficulty to question

Revision ID: b7e2c4a1f901
Revises: fb1c0be1ebd7
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7e2c4a1f901"
down_revision = "fb1c0be1ebd7"
branch_labels = None
depends_on = None


def upgrade():
    # Existing questions start at the neutral midpoint (3). We intentionally do
    # not manufacture a 1-5 pedagogical classification from sort order or CEFR.
    op.add_column(
        "question",
        sa.Column(
            "level_difficulty",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
    )
    op.create_check_constraint(
        "ck_question_level_difficulty_1_5",
        "question",
        "level_difficulty >= 1 AND level_difficulty <= 5",
    )


def downgrade():
    op.drop_constraint(
        "ck_question_level_difficulty_1_5",
        "question",
        type_="check",
    )
    op.drop_column("question", "level_difficulty")
