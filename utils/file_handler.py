# ==========================================================
# 01. FILE HANDLER
# Validasi dan penyimpanan aman untuk gambar serta dokumen PDF.
# ==========================================================

"""Validasi dan penyimpanan aman untuk gambar serta dokumen PDF."""

from pathlib import Path, PurePosixPath
from uuid import uuid4

from flask import current_app
from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS | {"pdf"}
IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png"}
UNSAFE_PDF_MARKERS = (
    b"/JavaScript",
    b"/JS",
    b"/Launch",
    b"/EmbeddedFile",
    b"/OpenAction",
)
Image.MAX_IMAGE_PIXELS = 25_000_000


# Mengukur ukuran unggahan lalu mengembalikan posisi stream ke awal.
def _file_size(file):
    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    return size


# Memastikan folder tujuan tetap di bawah root unggahan dan membuatnya jika perlu.
def _safe_folder(root, folder):
    relative = PurePosixPath(folder)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Lokasi penyimpanan tidak valid.")
    destination = (Path(root) / Path(*relative.parts)).resolve()
    root = Path(root).resolve()
    if destination != root and root not in destination.parents:
        raise ValueError("Lokasi penyimpanan tidak valid.")
    destination.mkdir(parents=True, exist_ok=True)
    return destination


# Memvalidasi isi JPEG atau PNG lalu menyimpan ulang dengan nama acak.
def _save_image(file, destination, optimize_image):
    path = None
    try:
        file.stream.seek(0)
        with Image.open(file.stream) as probe:
            probe.verify()
            detected_format = probe.format
        extension = IMAGE_FORMATS.get(detected_format)
        if not extension:
            raise ValueError("Isi file bukan gambar JPEG atau PNG yang valid.")

        filename = f"{uuid4().hex}.{extension}"
        path = destination / filename
        file.stream.seek(0)
        with Image.open(file.stream) as image:
            image.load()
            if image.width < 1 or image.height < 1:
                raise ValueError("Dimensi gambar tidak valid.")
            if optimize_image:
                image.thumbnail((1600, 1600))
            if detected_format == "JPEG":
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                image.save(path, "JPEG", optimize=True, quality=85)
            else:
                if image.mode not in {"RGB", "RGBA", "L", "LA"}:
                    image = image.convert("RGBA")
                image.save(path, "PNG", optimize=True)
        return filename
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        if path:
            path.unlink(missing_ok=True)
        raise ValueError("Isi file gambar rusak atau tidak aman.") from error


# Memeriksa penanda PDF dan menolak konten aktif sebelum menyimpan berkas.
def _save_pdf(file, destination):
    file.stream.seek(0)
    data = file.stream.read()
    file.stream.seek(0)
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ValueError("Isi file bukan PDF yang valid.")
    lowered = data.lower()
    if any(marker.lower() in lowered for marker in UNSAFE_PDF_MARKERS):
        raise ValueError("PDF aktif atau berisi lampiran tidak diizinkan.")
    filename = f"{uuid4().hex}.pdf"
    (destination / filename).write_bytes(data)
    return filename


def save_upload(
    file,
    folder,
    allowed=None,
    optimize_image=False,
    *,
    private=True,
):
    """Validate by content, sanitize, and store an uploaded file safely."""
    if not file or not file.filename:
        return None
    allowed = allowed or DOCUMENT_EXTENSIONS
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in allowed:
        raise ValueError("Format file tidak didukung.")
    size = _file_size(file)
    if size < 1:
        raise ValueError("File kosong tidak dapat diunggah.")
    if size > current_app.config["MAX_FILE_SIZE"]:
        raise ValueError("Ukuran file melebihi batas 2 MB.")

    root_key = "PRIVATE_UPLOAD_FOLDER" if private else "PUBLIC_UPLOAD_FOLDER"
    destination = _safe_folder(current_app.config[root_key], folder)
    if extension in IMAGE_EXTENSIONS:
        filename = _save_image(file, destination, optimize_image)
    elif extension == "pdf" and "pdf" in allowed:
        filename = _save_pdf(file, destination)
    else:
        raise ValueError("Format file tidak didukung.")
    return f"{PurePosixPath(folder)}/{filename}"


def delete_upload(relative_path, *, private=True, required_prefix=None):
    """Menghapus unggahan terkontrol tanpa pernah keluar dari root penyimpanan."""
    if not relative_path:
        return False
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    if required_prefix and (not relative.parts or relative.parts[0] != required_prefix):
        return False
    root_key = "PRIVATE_UPLOAD_FOLDER" if private else "PUBLIC_UPLOAD_FOLDER"
    root = Path(current_app.config[root_key]).resolve()
    target = (root / Path(*relative.parts)).resolve()
    if root not in target.parents or not target.is_file():
        return False
    try:
        target.unlink()
    except OSError:
        current_app.logger.warning("Gagal menghapus unggahan lama %s", relative)
        return False
    return True
