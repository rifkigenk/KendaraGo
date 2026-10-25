"""Pembuat laporan Excel dan invoice PDF dari data penyewaan."""

from io import BytesIO

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas


# ==========================================================
# 01. KEAMANAN ISI EXCEL
# Mencegah teks masukan pengguna dianggap sebagai rumus oleh aplikasi Excel.
# ==========================================================
def excel_safe(value):
    """Mencegah teks pengguna dieksekusi sebagai formula saat laporan dibuka."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


# ==========================================================
# 02. LAPORAN PENYEWAAN EXCEL
# Menyusun daftar penyewaan menjadi workbook di memori untuk diunduh.
# ==========================================================
def rentals_excel(rentals):
    """Mengubah daftar penyewaan menjadi workbook Excel di memori."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Penyewaan"
    sheet.append(
        ["Kode", "Pelanggan", "Kendaraan", "Mulai", "Selesai", "Status", "Total"]
    )
    for item in rentals:
        sheet.append(
            [
                excel_safe(item.booking_code),
                excel_safe(item.customer_name),
                excel_safe(item.vehicle.name),
                item.start_date,
                item.end_date,
                item.status,
                float(item.total_payment),
            ]
        )
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


# ==========================================================
# 03. INVOICE PDF
# Membuat dokumen tagihan berisi identitas pesanan dan rincian biaya.
# ==========================================================
def invoice_pdf(rental):
    """Menghasilkan dokumen invoice PDF untuk satu penyewaan."""
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=A4)
    canvas.setTitle(f"Invoice {rental.booking_code}")
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(50, 800, "KendaraGo")
    canvas.setFont("Helvetica", 11)
    lines = [
        f"Invoice: {rental.booking_code}",
        f"Pelanggan: {rental.customer_name}",
        f"Kendaraan: {rental.vehicle.name} ({rental.vehicle.license_plate})",
        f"Periode: {rental.start_date:%d-%m-%Y} s/d {rental.end_date:%d-%m-%Y}",
        f"Durasi: {rental.duration_days} hari",
        f"Status: {rental.status}",
        f"Subtotal kendaraan: Rp {rental.vehicle_subtotal:,.0f}",
        f"Biaya pengemudi: Rp {rental.driver_fee:,.0f}",
        f"Diskon: Rp {rental.discount:,.0f}",
        f"Deposit: Rp {rental.deposit:,.0f}",
        f"Total: Rp {rental.total_payment:,.0f}",
    ]
    for index, line in enumerate(lines):
        canvas.drawString(50, 760 - index * 24, line)
    canvas.save()
    stream.seek(0)
    return stream
