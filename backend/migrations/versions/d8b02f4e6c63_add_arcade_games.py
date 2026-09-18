"""add arcade games

Revision ID: d8b02f4e6c63
Revises: c7a91e3d5b52
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'd8b02f4e6c63'
down_revision = 'c7a91e3d5b52'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'arcade_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_type', sa.String(length=40), nullable=False),
        sa.Column('level_code', sa.String(length=10), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('rounds_total', sa.Integer(), nullable=False),
        sa.Column('rounds_correct', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_arcade_run_user_started', 'arcade_run', ['user_id', 'started_at'])
    op.create_table(
        'arcade_challenge',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('arcade_run_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=30), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('correct_answer', sa.Text(), nullable=False),
        sa.Column('selected_answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['arcade_run_id'], ['arcade_run.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('arcade_challenge')
    op.drop_index('ix_arcade_run_user_started', table_name='arcade_run')
    op.drop_table('arcade_run')
