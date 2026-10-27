"""Add booking identity snapshots without changing historical bookings."""

from alembic import op
import sqlalchemy as sa

revision = "d93c30ec2026"
down_revision = "c82b20db2026"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rentals") as batch:
        batch.add_column(sa.Column("identity_type", sa.String(12), nullable=True))
        batch.add_column(sa.Column("identity_number", sa.String(32), nullable=True))
        batch.add_column(sa.Column("identity_country", sa.String(80), nullable=True))


def downgrade():
    raise RuntimeError(
        "Ekspor dan tinjau identitas penyewa sebelum menurunkan migrasi ini."
    )
