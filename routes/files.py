"""Route berkas privat dengan pemeriksaan hak akses sebelum file dikirim."""

from pathlib import Path, PurePosixPath

from flask import Blueprint, abort, current_app, send_from_directory
from flask_login import current_user, login_required

from models import CustomerProfile, Payment, VehiclePickup, VehicleReturn


bp = Blueprint("files", __name__, url_prefix="/berkas")


# ==========================================================
# 01. PENGIRIMAN BERKAS PRIVAT
# Memastikan file berasal dari PRIVATE_UPLOAD_FOLDER sebelum dikirim.
# ==========================================================
def send_private_file(relative_path):
    """Mengirim file hanya dari folder privat yang telah ditentukan."""
    if not relative_path:
        abort(404)
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        abort(404)
    root = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]).resolve()
    target = (root / Path(*relative.parts)).resolve()
    if root not in target.parents or not target.is_file():
        abort(404)
    return send_from_directory(
        root,
        str(relative),
        as_attachment=True,
        download_name=target.name,
        max_age=0,
    )


# ==========================================================
# 02. FOTO PROFIL DAN DOKUMEN IDENTITAS
# Foto profil, KTP, dan SIM hanya dapat diunduh oleh pemilik atau admin.
# ==========================================================
# Memeriksa hak akses sebelum mengirim dokumen identitas privat.
@bp.route("/profil/<int:profile_id>/<field>")
@login_required
def profile_document(profile_id, field):
    allowed_fields = {"profile_image", "ktp_image", "sim_image"}
    if field not in allowed_fields:
        abort(404)
    profile = CustomerProfile.query.get_or_404(profile_id)
    if current_user.role != "admin" and current_user.id != profile.user_id:
        abort(403)
    return send_private_file(getattr(profile, field))


# ==========================================================
# 03. BUKTI PEMBAYARAN
# Memeriksa pemilik pesanan atau peran admin sebelum mengirim bukti.
# ==========================================================
# Memeriksa hak akses sebelum mengirim bukti pembayaran privat.
@bp.route("/pembayaran/<int:payment_id>")
@login_required
def payment_proof(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if current_user.role != "admin" and current_user.id != payment.rental.customer_id:
        abort(403)
    return send_private_file(payment.proof_file)


# ==========================================================
# 04. FOTO PEMERIKSAAN
# Mengizinkan pemilik pesanan, petugas, atau admin mengunduh foto kondisi.
# ==========================================================
# Memeriksa hak akses sebelum mengirim foto pemeriksaan privat.
@bp.route("/pemeriksaan/<kind>/<int:item_id>")
@login_required
def inspection_photo(kind, item_id):
    model = {"pengambilan": VehiclePickup, "pengembalian": VehicleReturn}.get(kind)
    if model is None:
        abort(404)
    item = model.query.get_or_404(item_id)
    if (
        current_user.role not in {"admin", "petugas"}
        and current_user.id != item.rental.customer_id
    ):
        abort(403)
    return send_private_file(item.photo)
