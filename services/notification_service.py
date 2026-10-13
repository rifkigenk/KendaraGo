"""Layanan kecil untuk membuat notifikasi pengguna secara konsisten."""

from extensions import db
from models import Notification


def notify(user_id, title, message, link=None, commit=False):
    """Menambahkan notifikasi; commit opsional dipakai untuk transaksi mandiri."""
    notification = Notification(
        user_id=user_id, title=title, message=message, link=link
    )
    db.session.add(notification)
    if commit:
        db.session.commit()
    return notification
