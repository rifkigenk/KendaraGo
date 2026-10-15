# ==========================================================
# 01. TEMPLATE REVISI MIGRASI
# Mako mengisi identitas revisi serta operasi upgrade dan downgrade saat revisi dibuat.
# ==========================================================

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Identitas revisi menghubungkan perubahan ini dengan revisi sebelumnya.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


# Terapkan perubahan skema pada revisi ini.
def upgrade():
    ${upgrades if upgrades else "pass"}


# Kembalikan skema ke revisi sebelumnya.
def downgrade():
    ${downgrades if downgrades else "pass"}
