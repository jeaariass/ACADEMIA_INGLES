"""add writing practice

Revision ID: c7a91e3d5b52
Revises: b6e4f10a2c41
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'c7a91e3d5b52'
down_revision = 'b6e4f10a2c41'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'writing_prompt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('level_code', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('min_words', sa.Integer(), nullable=False),
        sa.Column('max_words', sa.Integer(), nullable=False),
        sa.Column('target_vocabulary', sa.JSON(), nullable=False),
        sa.Column('target_connectors', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_table(
        'writing_submission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('prompt_id', sa.Integer(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('sentence_count', sa.Integer(), nullable=False),
        sa.Column('unique_word_ratio', sa.Float(), nullable=True),
        sa.Column('target_hits', sa.Integer(), nullable=False),
        sa.Column('connector_hits', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['prompt_id'], ['writing_prompt.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'prompt_id', 'revision_number', name='uq_writing_revision'),
    )
    op.create_index('ix_writing_submission_user_created', 'writing_submission', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_writing_submission_user_created', table_name='writing_submission')
    op.drop_table('writing_submission')
    op.drop_table('writing_prompt')
