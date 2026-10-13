"""add rental payment deadline

Revision ID: 420ec1b3d2f7
Revises: 3a0cc36b4214
Create Date: 2026-10-09 13:26:07.834910

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "420ec1b3d2f7"
down_revision = "3a0cc36b4214"
branch_labels = None
depends_on = None


def upgrade():
    # Tambahkan sebagai nullable dahulu agar database lama yang sudah berisi
    # transaksi dapat dimigrasikan tanpa kehilangan data.
    with op.batch_alter_table("rentals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_due_at", sa.DateTime(), nullable=True))
    op.execute(sa.text("UPDATE rentals SET payment_due_at = created_at"))
    with op.batch_alter_table("rentals", schema=None) as batch_op:
        batch_op.alter_column(
            "payment_due_at", existing_type=sa.DateTime(), nullable=False
        )
        batch_op.create_index(
            batch_op.f("ix_rentals_payment_due_at"),
            ["payment_due_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("rentals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rentals_payment_due_at"))
        batch_op.drop_column("payment_due_at")
