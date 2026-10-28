"""Blanko Excel gabungan: Musyrif + Kelas + Siswa dalam satu tabel/file."""

import os
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import Config

HEADER_FILL = PatternFill("solid", fgColor="0F6B4C")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)

# Satu tabel gabungan — tiap baris = 1 siswa + data kelas & musyrif terkait
COMBINED_HEADERS = [
    "kode_musyrif",
    "nama_musyrif",
    "gelar_musyrif",
    "telepon_musyrif",
    "nama_kelas",
    "jenjang",
    "nis",
    "nama_siswa",
    "jenis_kelamin",
    "nama_orang_tua",
    "telepon_orang_tua",
]

COMBINED_CONTOH = [
    ["M001", "Abdullah", "S.Pd.I", "081234567890", "8-A", 8, "2507001", "Ahmad Fauzan", "L", "Budi Santoso", "081211111111"],
    ["M001", "Abdullah", "S.Pd.I", "081234567890", "8-A", 8, "2507002", "Rizki Pratama", "L", "Agus Wijaya", "081222222222"],
    ["M002", "Aisyah", "Lc.", "081298765432", "7-B", 7, "2507003", "Fatimah Zahra", "P", "Siti Aminah", "081233333333"],
    ["M002", "Aisyah", "Lc.", "081298765432", "9-A", 9, "2507004", "Nur Aini", "P", "Hasan Basri", "081244444444"],
]

FILENAME = "blanko_data_tahfidz.xlsx"
SHEET_NAME = "Data Tahfidz"


def _style_header(ws, col_count):
    for col in range(1, col_count + 1):
        cell = ws.cell(1, col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN


def generate_blanko_combined() -> BytesIO:
    """Satu file Excel, satu sheet: musyrif + kelas + siswa."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    for i, h in enumerate(COMBINED_HEADERS, 1):
        ws.cell(1, i, h)
    _style_header(ws, len(COMBINED_HEADERS))
    ws.row_dimensions[1].height = 28

    for r, row in enumerate(COMBINED_CONTOH, 2):
        for c, val in enumerate(row, 1):
            cell = ws.cell(r, c, val)
            cell.border = THIN

    widths = [14, 18, 12, 16, 12, 10, 12, 20, 12, 18, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    tip = wb.create_sheet("Petunjuk", 0)
    tip["A1"] = "Blanko Data Tahfidz — Satu Tabel"
    tip["A1"].font = Font(bold=True, size=14, color="0F6B4C")
    tip["A3"] = "Sekolah"
    tip["B3"] = Config.SCHOOL_NAME
    tip["A4"] = "Isi"
    tip["B4"] = (
        "Satu baris = satu siswa. Kolom musyrif & kelas diulang pada setiap baris siswa "
        "yang sama musyrif/kelasnya. Sistem akan otomatis membuat/memperbarui "
        "data Musyrif, Kelas, dan Siswa dari file ini."
    )
    tip["A5"] = "Kolom wajib"
    tip["B5"] = (
        "kode_musyrif, nama_musyrif, nama_kelas, jenjang (7/8/9), nis, nama_siswa, jenis_kelamin (L/P)"
    )
    tip["A6"] = "Opsional"
    tip["B6"] = "gelar_musyrif, telepon_musyrif, nama_orang_tua, telepon_orang_tua"
    tip["A7"] = "Login ortu"
    tip["B7"] = (
        "nama_orang_tua = username login orang tua. Password awal = password default sistem."
    )
    tip["A8"] = "Catatan"
    tip["B8"] = (
        "Hapus baris contoh sebelum upload (atau biarkan — ikut terimpor). "
        "Baris kosong dilewati. Data terikat ke TAHUN AJARAN yang sedang dipilih di aplikasi. "
        "Jika kode_musyrif / nama_kelas / nis sudah ada, data diperbarui (upsert)."
    )
    tip.column_dimensions["A"].width = 14
    tip.column_dimensions["B"].width = 100

    os.makedirs(Config.BLANKO_FOLDER, exist_ok=True)
    path = os.path.join(Config.BLANKO_FOLDER, FILENAME)
    wb.save(path)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def parse_blanko_combined(file_storage):
    """Parse satu sheet gabungan → list dict per baris siswa."""
    wb = load_workbook(file_storage, data_only=True)
    if SHEET_NAME in wb.sheetnames:
        ws = wb[SHEET_NAME]
    elif "Data" in wb.sheetnames:
        ws = wb["Data"]
    else:
        # ambil sheet pertama yang bukan Petunjuk
        ws = None
        for name in wb.sheetnames:
            if name.lower() != "petunjuk":
                ws = wb[name]
                break
        if ws is None:
            ws = wb.active

    expected = [h.lower() for h in COMBINED_HEADERS]
    first_row = [
        str(c.value).strip().lower() if c.value is not None else "" for c in ws[1]
    ]
    # Terima jika header lengkap, atau subset yang memuat field inti
    if first_row[: len(expected)] != expected:
        # coba cocokkan dengan alias lama (blanko terpisah digabung manual)
        raise ValueError(
            "Header tidak sesuai blanko gabungan. "
            f"Harus: {', '.join(COMBINED_HEADERS)}. "
            f"Ditemukan: {', '.join([x for x in first_row if x][:12])}"
        )

    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(v is None or str(v).strip() == "" for v in row):
            continue
        item = {}
        for i, key in enumerate(COMBINED_HEADERS):
            val = row[i] if i < len(row) else None
            if val is None:
                item[key] = ""
            else:
                item[key] = str(val).strip()
        # Minimal harus ada nis + nama siswa ATAU cukup data musyrif/kelas saja?
        # Kita izinkan baris yang hanya musyrif (tanpa nis) untuk daftar musyrif saja,
        # dan baris kelas tanpa siswa — tapi praktik: baris dengan nis diimpor sebagai siswa.
        rows.append(item)
    return rows


# Kompatibilitas nama lama (dipakai import di app jika masih ada)
def generate_blanko(jenis: str = "combined") -> BytesIO:
    return generate_blanko_combined()


def parse_blanko(jenis: str, file_storage):
    return parse_blanko_combined(file_storage)