"""add_session_feedback_category_and_unique_event

Revision ID: d8b5c2a1e3f4
Revises: 621aa6c6d813
Create Date: 2026-10-05 15:30:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b5c2a1e3f4'
down_revision: Union[str, None] = '621aa6c6d813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add structured category column to session_feedback for missed detections and categorization
    op.add_column('session_feedback', sa.Column('category', sa.String(length=50), nullable=True))

    # 2. Add partial unique index on (session_id, detection_event_id) where detection_event_id is not null
    # to prevent duplicate feedback records for the same detection event and enable idempotent upserts
    op.create_index(
        'uq_session_feedback_session_event',
        'session_feedback',
        ['session_id', 'detection_event_id'],
        unique=True,
        postgresql_where=sa.text('detection_event_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_session_feedback_session_event',
        table_name='session_feedback',
        postgresql_where=sa.text('detection_event_id IS NOT NULL'),
    )
    op.drop_column('session_feedback', 'category')
