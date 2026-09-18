"""add library and saved vocabulary

Revision ID: f4b8c21d7a10
Revises: e8c31d7a4205
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa


revision = "f4b8c21d7a10"
down_revision = "e8c31d7a4205"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "library_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("level_code", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "saved_vocabulary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("library_item_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.String(length=220), nullable=False),
        sa.Column("normalized_text", sa.String(length=220), nullable=False),
        sa.Column("translation", sa.String(length=500), nullable=False),
        sa.Column("context_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("review_stage", sa.Integer(), nullable=False),
        sa.Column("mastery_level", sa.Integer(), nullable=False),
        sa.Column("correct_reviews", sa.Integer(), nullable=False),
        sa.Column("incorrect_reviews", sa.Integer(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["library_item_id"], ["library_item.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "normalized_text",
            name="uq_saved_vocabulary_user_text",
        ),
    )

    op.create_index(
        "ix_saved_vocabulary_due",
        "saved_vocabulary",
        ["user_id", "next_review_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_saved_vocabulary_due", table_name="saved_vocabulary")
    op.drop_table("saved_vocabulary")
    op.drop_table("library_item")
