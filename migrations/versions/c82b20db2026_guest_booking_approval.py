# ==========================================================
# 01. MIGRASI PEMESANAN TAMU
# Mengizinkan pesanan tanpa akun serta menyimpan kontak dan kunci sesi tamu untuk membatasi akses.
# ==========================================================

"""Guest bookings share the rental and approval workflow."""

from alembic import op
import sqlalchemy as sa

revision = "c82b20db2026"
down_revision = "b71a10ca2026"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rentals") as batch:
        batch.alter_column("customer_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("guest_name", sa.String(120), nullable=True))
        batch.add_column(sa.Column("guest_phone", sa.String(20), nullable=True))
        batch.add_column(sa.Column("guest_session_key", sa.String(64), nullable=True))
        batch.create_index("ix_rentals_guest_session_key", ["guest_session_key"])
        batch.create_unique_constraint(
            "uq_guest_rental_request", ["guest_session_key", "request_key"]
        )


def downgrade():
    raise RuntimeError("Ekspor dan tinjau pesanan tamu sebelum menurunkan migrasi ini.")
