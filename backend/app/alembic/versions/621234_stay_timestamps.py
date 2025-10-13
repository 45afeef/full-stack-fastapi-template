"""add timestamps to stay related tables

Revision ID: 621234stayts
Revises: 51898cd753b2
Create Date: 2025-10-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '621234stayts'
down_revision = '51898cd753b2'
branch_labels = None
depends_on = None


def upgrade():
    # # add created_at and updated_at to stay related tables
    # tables = [
    #     "serviceprovider",
    #     "stayserviceprovider",
    #     "stayunit",
    #     "travelagency",
    #     "travelagencystaff",
    # ]
    # for t in tables:
    #     op.add_column(
    #         t,
    #         sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    #     )
    #     op.add_column(
    #         t,
    #         sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    #     )
    pass


def downgrade():
    # tables = [
    #     "serviceprovider",
    #     "stayserviceprovider",
    #     "stayunit",
    #     "travelagency",
    #     "travelagencystaff",
    # ]
    # for t in tables:
    #     op.drop_column(t, "updated_at")
    #     op.drop_column(t, "created_at")
    pass
