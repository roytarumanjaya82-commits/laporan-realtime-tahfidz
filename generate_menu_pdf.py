"""Ambil screenshot tiap menu admin lalu susun ke PDF."""

from __future__ import annotations

import io
import os
from pathlib import Path

from playwright.sync_api import sync_playwright
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PIL import Image

BASE = "http://127.0.0.1:5000"
ROOT = Path(__file__).resolve().parent
SHOT_DIR = ROOT / "docs" / "menu_shots"
PDF_PATH = ROOT / "docs" / "Tampilan_Menu_Tahfidz_Realtime.pdf"

# urutan halaman katalog (admin)
PAGES = [
    ("01_login", "/login", "Login", False),
    ("02_dashboard", "/", "Dashboard Realtime", True),
    ("03_setoran", "/setoran", "Setoran Realtime", True),
    ("04_laporan", "/laporan", "Laporan Murid", True),
    ("05_siswa", "/siswa", "Data Siswa", True),
    ("06_pindah_musyrif", "/siswa/pindah-musyrif", "Pindah Musyrif", True),
    ("07_kelas", "/kelas", "Data Kelas", True),
    ("08_musyrif", "/musyrif", "Data Musyrif", True),
    ("09_blanko", "/blanko", "Blanko Unduh / Upload", True),
    ("10_tahun_ajaran", "/tahun-ajaran", "Tahun Ajaran", True),
    ("11_orang_tua", "/orang-tua", "Akun Orang Tua", True),
    ("12_users", "/users", "Pengguna Staf", True),
    ("13_ganti_password", "/ganti-password", "Ganti Password", True),
]


def capture():
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            device_scale_factor=1.25,
        )
        page = context.new_page()

        # login dulu
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        for slug, path, title, need_auth in PAGES:
            if path == "/login":
                # buka login di context terpisah tanpa session
                page2 = context.new_page()
                # logout first in main? better open fresh context for login shot
                page2.close()
                login_ctx = browser.new_context(
                    viewport={"width": 1366, "height": 900},
                    device_scale_factor=1.25,
                )
                lp = login_ctx.new_page()
                lp.goto(f"{BASE}/login", wait_until="networkidle")
                out = SHOT_DIR / f"{slug}.png"
                lp.screenshot(path=str(out), full_page=True)
                login_ctx.close()
            else:
                page.goto(f"{BASE}{path}", wait_until="networkidle")
                page.wait_for_timeout(400)
                out = SHOT_DIR / f"{slug}.png"
                page.screenshot(path=str(out), full_page=True)
            files.append((title, out))
            print(f"✓ {title} -> {out.name}")

        browser.close()
    return files


def fit_image(path: Path, max_w: float, max_h: float):
    im = Image.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h)
    return w * scale, h * scale, im


def build_pdf(files):
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    # cover
    c.setFillColorRGB(0.04, 0.24, 0.18)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(page_w / 2, page_h / 2 + 40, "Tampilan Menu Aplikasi")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(page_w / 2, page_h / 2 + 12, "Laporan Hasil Belajar Tahfidz Realtime")
    c.setFont("Helvetica", 11)
    c.drawCentredString(page_w / 2, page_h / 2 - 14, "SMP Muhammadiyah 22 Setiabudi Pamulang")
    c.setFont("Helvetica", 9)
    c.drawCentredString(page_w / 2, page_h / 2 - 36, "Jenjang 7–9 · Target Lulus 4 Juz")
    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, 28 * mm, "Dokumen katalog antarmuka (screenshot per menu)")
    c.showPage()

    # daftar isi
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.04, 0.24, 0.18)
    c.drawString(margin, page_h - 25 * mm, "Daftar Menu")
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.1, 0.18, 0.16)
    y = page_h - 38 * mm
    for i, (title, _) in enumerate(files, 1):
        c.drawString(margin, y, f"{i}. {title}")
        y -= 8 * mm
        if y < 25 * mm:
            c.showPage()
            y = page_h - 25 * mm
    c.showPage()

    # tiap menu 1 halaman
    for i, (title, path) in enumerate(files, 1):
        c.setFillColorRGB(0.04, 0.24, 0.18)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, page_h - 16 * mm, f"{i}. {title}")
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.35, 0.45, 0.4)
        c.drawString(margin, page_h - 21 * mm, str(path.name))

        max_w = page_w - 2 * margin
        max_h = page_h - 32 * mm
        disp_w, disp_h, im = fit_image(path, max_w, max_h)
        # convert to RGB for PDF
        if im.mode in ("RGBA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            if im.mode == "P":
                im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)
        x = (page_w - disp_w) / 2
        y = page_h - 24 * mm - disp_h
        c.drawImage(ImageReader(buf), x, y, width=disp_w, height=disp_h, preserveAspectRatio=True, mask="auto")
        c.showPage()
        print(f"PDF page: {title}")

    c.save()
    print(f"\nPDF siap: {PDF_PATH}")


if __name__ == "__main__":
    shots = capture()
    build_pdf(shots)
