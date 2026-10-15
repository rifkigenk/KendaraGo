"""Add WhatsApp consent, deduplication and outbox tables."""

from alembic import op
import sqlalchemy as sa

revision = "9c10a1b2c3d4"
down_revision = "420ec1b3d2f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_contacts",
        sa.Column("phone", sa.String(20), primary_key=True),
        sa.Column("opted_in", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "whatsapp_events",
        sa.Column("message_id", sa.String(255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "whatsapp_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("meta_message_id", sa.String(255)),
        sa.Column("error", sa.String(120)),
    )
    op.create_index("ix_whatsapp_outbox_status", "whatsapp_outbox", ["status"])


def downgrade():
    op.drop_table("whatsapp_outbox")
    op.drop_table("whatsapp_events")
    op.drop_table("whatsapp_contacts")
