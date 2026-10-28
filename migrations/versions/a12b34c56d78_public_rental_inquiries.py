# ==========================================================
# 01. MIGRASI PERMINTAAN SEWA PUBLIK
# Menambahkan penyimpanan permintaan sewa awal yang dikirim melalui halaman publik.
# ==========================================================

"""Store public rental requests for admin follow-up."""

from alembic import op
import sqlalchemy as sa


revision = "a12b34c56d78"
down_revision = "9c10a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rental_inquiries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=True),
        sa.Column("pickup_location_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("nik", sa.String(length=16), nullable=False),
        sa.Column("whatsapp", sa.String(length=20), nullable=False),
        sa.Column("emergency_phone", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("pickup_time", sa.Time(), nullable=False),
        sa.Column("with_driver", sa.Boolean(), nullable=False),
        sa.Column("sim_type", sa.String(length=20), nullable=True),
        sa.Column("sim_number", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"]),
        sa.ForeignKeyConstraint(["pickup_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rental_inquiries_vehicle_id", "rental_inquiries", ["vehicle_id"]
    )
    op.create_index("ix_rental_inquiries_driver_id", "rental_inquiries", ["driver_id"])
    op.create_index("ix_rental_inquiries_status", "rental_inquiries", ["status"])


def downgrade():
    op.drop_index("ix_rental_inquiries_status", table_name="rental_inquiries")
    op.drop_index("ix_rental_inquiries_driver_id", table_name="rental_inquiries")
    op.drop_index("ix_rental_inquiries_vehicle_id", table_name="rental_inquiries")
    op.drop_table("rental_inquiries")
