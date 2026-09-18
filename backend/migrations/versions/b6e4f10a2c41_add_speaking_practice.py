"""add speaking practice

Revision ID: b6e4f10a2c41
Revises: a2d5f61e9c30
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'b6e4f10a2c41'
down_revision = 'a2d5f61e9c30'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'speaking_exercise',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('level_code', sa.String(length=10), nullable=False),
        sa.Column('activity_type', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('expected_text', sa.Text(), nullable=True),
        sa.Column('target_vocabulary', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_table(
        'speaking_attempt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('recognition_confidence', sa.Float(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('token_coverage', sa.Float(), nullable=True),
        sa.Column('words_per_minute', sa.Float(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('target_hits', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['exercise_id'], ['speaking_exercise.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_speaking_attempt_user_created', 'speaking_attempt', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_speaking_attempt_user_created', table_name='speaking_attempt')
    op.drop_table('speaking_attempt')
    op.drop_table('speaking_exercise')
