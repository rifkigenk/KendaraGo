"""Bali location snapshots and retry-safe bookings; preserve historical data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "b71a10ca2026"
down_revision = "a12b34c56d78"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("locations") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(), type_=sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), existing_nullable=False)
        batch.add_column(sa.Column("address_data", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("verified_by_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_location_verified_by", "users", ["verified_by_id"], ["id"])
    with op.batch_alter_table("rentals") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(), type_=sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), existing_nullable=False)
        batch.alter_column("pickup_location_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("return_location_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("pickup_address", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("return_address", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("request_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("request_hash", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_rental_request", ["customer_id", "request_key"])


def downgrade():
    # Deliberately refuse a downgrade that would discard saved meeting points.
    raise RuntimeError("Ekspor dan tinjau data lokasi sebelum menurunkan migrasi ini.")
