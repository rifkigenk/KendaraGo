# ==========================================================
# 01. WSGI
# Entry point untuk server WSGI produksi.
# ==========================================================

"""Entry point untuk server WSGI produksi."""

from app import create_app


application = create_app()
