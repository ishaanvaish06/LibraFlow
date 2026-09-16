"""add outbox_events table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(64), nullable=False),
        sa.Column('topic', sa.String(128), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_outbox_events_event_id', 'outbox_events', ['event_id'], unique=True)
    op.create_index('ix_outbox_events_topic', 'outbox_events', ['topic'])
    op.create_index('ix_outbox_events_status', 'outbox_events', ['status'])


def downgrade() -> None:
    op.drop_table('outbox_events')
