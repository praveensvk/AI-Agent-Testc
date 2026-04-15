"""Add login auth fields to test_suites

Revision ID: 003_add_suite_auth_fields
Revises: 002_add_test_type
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_suite_auth_fields"
down_revision = "002_add_test_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_suites", sa.Column("login_url", sa.String(2048), nullable=True))
    op.add_column("test_suites", sa.Column("login_username", sa.String(255), nullable=True))
    op.add_column("test_suites", sa.Column("login_password", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("test_suites", "login_password")
    op.drop_column("test_suites", "login_username")
    op.drop_column("test_suites", "login_url")
