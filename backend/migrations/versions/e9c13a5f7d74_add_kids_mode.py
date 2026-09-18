"""add kids mode

Revision ID: e9c13a5f7d74
Revises: d8b02f4e6c63
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'e9c13a5f7d74'
down_revision = 'd8b02f4e6c63'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('learning_mode', sa.String(length=20), nullable=False, server_default='standard'))
    op.create_table(
        'kids_game_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_type', sa.String(length=40), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('theme', sa.String(length=30), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('rounds_total', sa.Integer(), nullable=False),
        sa.Column('rounds_success', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kids_game_run_user_started', 'kids_game_run', ['user_id', 'started_at'])
    op.create_table(
        'kids_word_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('word_key', sa.String(length=80), nullable=False),
        sa.Column('exposures', sa.Integer(), nullable=False),
        sa.Column('successes', sa.Integer(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'word_key', name='uq_kids_word_progress_user_word'),
    )


def downgrade():
    op.drop_table('kids_word_progress')
    op.drop_index('ix_kids_game_run_user_started', table_name='kids_game_run')
    op.drop_table('kids_game_run')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('learning_mode')
