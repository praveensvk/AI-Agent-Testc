"""add test_type to test_cases

Revision ID: 002
Revises: 001_initial_schema
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_test_type'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'test_cases',
        sa.Column('test_type', sa.String(50), nullable=False, server_default='functional'),
    )


def downgrade() -> None:
    op.drop_column('test_cases', 'test_type')
