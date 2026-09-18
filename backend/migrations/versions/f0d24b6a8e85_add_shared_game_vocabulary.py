"""add shared game vocabulary

Revision ID: f0d24b6a8e85
Revises: e9c13a5f7d74
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "f0d24b6a8e85"
down_revision = "e9c13a5f7d74"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "game_vocabulary_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("visual", sa.String(length=40), nullable=False, server_default="🎮"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kids_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("standard_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "game_vocabulary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("english", sa.String(length=160), nullable=False),
        sa.Column("spanish", sa.String(length=160), nullable=False),
        sa.Column("visual", sa.String(length=80), nullable=False, server_default="✨"),
        sa.Column("kids_difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cefr_level", sa.String(length=10), nullable=False, server_default="A1"),
        sa.Column("standard_difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("kids_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("standard_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("kids_games", sa.JSON(), nullable=False),
        sa.Column("arcade_games", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("kids_difficulty BETWEEN 1 AND 3", name="ck_game_vocab_kids_difficulty"),
        sa.CheckConstraint("standard_difficulty BETWEEN 1 AND 5", name="ck_game_vocab_standard_difficulty"),
        sa.ForeignKeyConstraint(["category_id"], ["game_vocabulary_category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_game_vocab_category", "game_vocabulary", ["category_id"])
    op.create_index("ix_game_vocab_cefr", "game_vocabulary", ["cefr_level", "standard_difficulty"])
    with op.batch_alter_table("game_challenge", schema=None) as batch_op:
        batch_op.add_column(sa.Column("game_vocabulary_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_game_challenge_game_vocabulary",
            "game_vocabulary",
            ["game_vocabulary_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("game_challenge", schema=None) as batch_op:
        batch_op.drop_constraint("fk_game_challenge_game_vocabulary", type_="foreignkey")
        batch_op.drop_column("game_vocabulary_id")
    op.drop_index("ix_game_vocab_cefr", table_name="game_vocabulary")
    op.drop_index("ix_game_vocab_category", table_name="game_vocabulary")
    op.drop_table("game_vocabulary")
    op.drop_table("game_vocabulary_category")
