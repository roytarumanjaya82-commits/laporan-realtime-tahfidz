"""PDF katalog tampilan menu & laporan orang tua (render template + screenshot)."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, session
from playwright.sync_api import sync_playwright
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
SHOT_DIR = ROOT / "docs" / "menu_shots_ortu"
PDF_PATH = ROOT / "docs" / "Tampilan_Menu_Laporan_Orang_Tua.pdf"
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
LOGO = ROOT / "static" / "img" / "logo-smpm22.png"

# Data contoh untuk dokumentasi (bukan akun produksi)
SAMPLE = {
    "school_name": "SMP Muhammadiyah 22 Setiabudi Pamulang",
    "app_title": "Laporan Hasil Belajar Tahfidz Realtime",
    "nama_ortu": "Budi Santoso",
    "anak": {
        "id": 1,
        "nis": "2507001",
        "nama": "Ahmad Fauzan",
        "nama_kelas": "8-A",
        "jenjang": 8,
        "nama_musyrif": "Abdullah",
        "gelar_musyrif": "S.Pd.I",
    },
}


def shell(body: str, title: str) -> str:
    logo_uri = LOGO.as_uri() if LOGO.exists() else ""
    return f"""<!DOCTYPE html>
<html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head><body>
<div class="app-shell">
  <aside class="sidebar open" style="position:relative;transform:none;left:0;height:auto;min-height:100vh">
    <div class="sidebar-head">
      <div class="brand">
        <img class="brand-logo" src="{logo_uri}" alt="Logo">
        <div class="brand-text">
          <div class="brand-mark">Tahfidz Realtime</div>
          <div class="brand-sub">{SAMPLE['school_name']}<br>Jenjang 7–9 · Target 4 Juz</div>
        </div>
      </div>
    </div>
    <nav class="nav">
      <div class="nav-section">Orang Tua</div>
      <a href="#" class="{'active' if 'Dashboard' in title or 'Perkembangan' in title else ''}">Perkembangan Anak</a>
      <a href="#" class="{'active' if 'Laporan' in title else ''}">Laporan Lengkap</a>
      <a href="#" class="{'active' if 'Password' in title else ''}">Ganti Password</a>
      <a href="#">Keluar</a>
    </nav>
  </aside>
  <div class="main">
    <header class="topbar">
      <div class="topbar-left">
        <img class="topbar-logo" src="{logo_uri}" alt="" style="display:block">
        <h1>{title}</h1>
      </div>
      <div class="topbar-meta">
        <span class="user-chip">2026/2027 · Sem 1</span>
        <span class="user-chip">{SAMPLE['nama_ortu']} (orang_tua)</span>
      </div>
    </header>
    <div class="content">{body}</div>
  </div>
</div>
</body></html>"""


def page_login() -> str:
    logo_uri = LOGO.as_uri() if LOGO.exists() else ""
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>
<div class="login-page">
  <div class="login-card">
    <div class="login-brand">
      <img class="login-logo" src="{logo_uri}" alt="Logo">
      <p class="logo">{SAMPLE['app_title']}</p>
      <p class="school">{SAMPLE['school_name']}</p>
    </div>
    <form>
      <div style="margin-bottom:1rem"><label>Username</label>
        <input type="text" value="{SAMPLE['nama_ortu']}" readonly></div>
      <div style="margin-bottom:1.25rem"><label>Password</label>
        <input type="password" value="••••••••" readonly></div>
      <button class="btn btn-primary" type="button" style="width:100%">Masuk</button>
    </form>
    <p style="margin-top:1.25rem;font-size:0.8rem;color:var(--muted);text-align:center;line-height:1.5">
      Orang tua: username = <strong>nama orang tua</strong>, password awal = password default sistem
    </p>
  </div>
</div>
</body></html>"""


def page_dashboard() -> str:
    a = SAMPLE["anak"]
    body = f"""
<p style="margin-top:0;color:var(--muted)">
  Halo, <strong>{SAMPLE['nama_ortu']}</strong>. Pantau hasil belajar tahfidz anak Anda secara realtime.
  Tahun ajaran: <strong>2026/2027</strong> · Semester 1.
</p>
<div class="grid grid-2" style="margin-bottom:1.25rem">
  <div class="panel">
    <div class="panel-header">
      <h2>{a['nama']}</h2>
      <a class="btn btn-sm btn-primary" href="#">Lihat Laporan</a>
    </div>
    <div class="panel-body">
      <div class="metric-cards parent-metrics" style="margin-bottom:0.75rem">
        <div class="metric"><div class="label">Kelas</div><div class="value" style="font-size:1.1rem">{a['nama_kelas']}</div></div>
        <div class="metric"><div class="label">Musyrif</div><div class="value" style="font-size:1.1rem">{a['nama_musyrif']}</div></div>
        <div class="metric"><div class="label">Capaian Hafalan</div><div class="value" style="font-size:1.15rem">1 Juz + 5 Halaman</div></div>
        <div class="metric"><div class="label">% Target Lulus (4 Juz)</div><div class="value" style="font-size:1.15rem">31.3%</div>
          <div class="progress-bar" style="margin-top:0.45rem"><span style="width:31.3%"></span></div>
        </div>
      </div>
      <span class="badge badge-warning">Perlu Perhatian</span>
      <span class="badge badge-muted">Target periode: 2.5 Juz</span>
    </div>
  </div>
</div>
<div class="panel">
  <div class="panel-header"><h2>Aktivitas Setoran Terbaru</h2></div>
  <div class="panel-body table-wrap">
    <table class="data">
      <thead><tr><th>Waktu</th><th>Anak</th><th>Jenis</th><th>Surah / Ayat</th><th>Volume</th><th>Nilai</th><th>Status</th></tr></thead>
      <tbody>
        <tr>
          <td>28/10/2026 07:30</td>
          <td>{a['nama']}<br><small>{a['nama_kelas']}</small></td>
          <td>Ziyadah</td>
          <td>Q.S. Al-Mujadila: 1–8 (Juz 28)</td>
          <td>1 hlm · 8 brs</td>
          <td>A (92) - Sangat Baik</td>
          <td><span class="badge badge-success">Lulus</span></td>
        </tr>
        <tr>
          <td>27/10/2026 07:30</td>
          <td>{a['nama']}<br><small>{a['nama_kelas']}</small></td>
          <td>Muraja'ah</td>
          <td>Q.S. Al-Mulk – An-Naba'</td>
          <td>3 hlm</td>
          <td>B (85) - Baik</td>
          <td><span class="badge badge-warning">Ulang</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>"""
    return shell(body, "Perkembangan Anak")


def page_laporan_index() -> str:
    a = SAMPLE["anak"]
    body = f"""
<div class="panel">
  <div class="panel-header">
    <h2>Progress Hafalan Realtime — 2026/2027 Sem 1</h2>
  </div>
  <div class="panel-body table-wrap">
    <table class="data">
      <thead>
        <tr><th>NIS</th><th>Nama</th><th>Kelas</th><th>Musyrif</th><th>Capaian</th><th>Target</th><th>% Lulus (4 Juz)</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr>
          <td>{a['nis']}</td>
          <td><strong>{a['nama']}</strong></td>
          <td>{a['nama_kelas']}</td>
          <td>{a['nama_musyrif']}</td>
          <td>1 Juz + 5 Halaman</td>
          <td>2.5 Juz</td>
          <td style="min-width:130px">
            <div class="progress-bar"><span style="width:31.3%"></span></div>
            <small>31.3%</small>
          </td>
          <td><span class="badge badge-warning">Perlu Perhatian</span></td>
          <td><a class="btn btn-sm btn-primary" href="#">Detail</a></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
<p style="color:var(--muted);font-size:0.9rem">Orang tua hanya melihat data anak yang terhubung ke akunnya.</p>"""
    return shell(body, "Laporan Lengkap")


def page_laporan_detail() -> str:
    a = SAMPLE["anak"]
    logo_uri = LOGO.as_uri() if LOGO.exists() else ""
    body = f"""
<div class="report-hero">
  <div class="report-hero-top">
    <img class="report-logo" src="{logo_uri}" alt="Logo">
    <div>
      <div class="report-school">{SAMPLE['school_name']}</div>
      <h2>{a['nama']}</h2>
      <div style="opacity:0.85;font-size:0.95rem">Laporan Hasil Belajar Tahfidz Al-Qur'an Realtime · Jenjang {a['jenjang']} SMP</div>
    </div>
  </div>
  <div class="meta">
    <div><span>Kelas / Jenjang</span><strong>{a['nama_kelas']} / {a['jenjang']} SMP</strong></div>
    <div><span>Tahun Ajaran</span><strong>2026/2027 · Semester 1</strong></div>
    <div><span>Musyrif Pembimbing</span><strong>Ustadz/ah {a['nama_musyrif']}, {a['gelar_musyrif']}</strong></div>
    <div><span>Target Total (3 Tahun)</span><strong>4 Juz (Juz 30, 29, 28, 27)</strong></div>
    <div><span>NIS</span><strong>{a['nis']}</strong></div>
    <div><span>Status Sistem</span><strong>Realtime Sync (Aktif)</strong></div>
  </div>
</div>
<div class="metric-cards">
  <div class="metric"><div class="label">Total Capaian Hafalan</div><div class="value">1 Juz + 5 Halaman</div></div>
  <div class="metric"><div class="label">Target Kumulatif Saat Ini</div><div class="value">2.5 Juz</div></div>
  <div class="metric"><div class="label">% Ketercapaian Target Lulus</div><div class="value">31.3%</div>
    <div class="progress-bar" style="margin-top:0.5rem"><span style="width:31.3%"></span></div></div>
  <div class="metric"><div class="label">Status Capaian</div><div class="value" style="font-size:1.1rem"><span class="badge badge-warning">Perlu Perhatian</span></div></div>
</div>
<div class="panel" style="margin-bottom:1.25rem">
  <div class="panel-header"><h2>III. Log Setoran Harian (Rekapitulasi Realtime)</h2></div>
  <div class="panel-body table-wrap">
    <table class="data">
      <thead><tr><th>Tanggal & Waktu</th><th>Jenis</th><th>Surah / Ayat</th><th>Volume</th><th>Nilai & Kualitas</th><th>Status</th><th>Catatan Musyrif</th></tr></thead>
      <tbody>
        <tr>
          <td>28 Okt 2026 · 07:30 WIB</td><td>Ziyadah</td><td>Q.S. Al-Mujadila: 1–8 (Juz 28)</td>
          <td>1 Halaman · 8 Baris</td><td>A (92) - Sangat Baik</td>
          <td><span class="badge badge-success">Lulus</span></td>
          <td>Makhraj huruf tepat, kelancaran sangat baik.</td>
        </tr>
        <tr>
          <td>27 Okt 2026 · 07:30 WIB</td><td>Muraja'ah</td><td>Q.S. Al-Mulk – An-Naba'</td>
          <td>3 Halaman</td><td>B (85) - Baik</td>
          <td><span class="badge badge-warning">Ulang</span></td>
          <td>Perhatikan hukum Ikhfa.</td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
<div class="grid grid-2">
  <div class="panel">
    <div class="panel-header"><h2>IV. Evaluasi Kualitas & Kelancaran</h2></div>
    <div class="panel-body table-wrap">
      <table class="data">
        <thead><tr><th>No</th><th>Elemen Evaluasi</th><th>Nilai</th><th>Predikat</th></tr></thead>
        <tbody>
          <tr><td>1</td><td>Kelancaran Hafalan (Fashohah / Mutqin)</td><td>90 / 100</td><td>Sangat Baik</td></tr>
          <tr><td>2</td><td>Ketepatan Hukum Tajwid & Mad</td><td>88 / 100</td><td>Baik</td></tr>
          <tr><td>3</td><td>Makharijul Huruf & Sifat Huruf</td><td>85 / 100</td><td>Baik</td></tr>
          <tr><td>4</td><td>Adab, Kehadiran, & Kedisiplinan Halaqah</td><td>95 / 100</td><td>Sangat Baik</td></tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header"><h2>V. Pemetaan Target Hafalan</h2></div>
    <div class="panel-body table-wrap">
      <table class="data">
        <thead><tr><th>Tingkat</th><th>Periode</th><th>Target</th><th>Kumulatif</th></tr></thead>
        <tbody>
          <tr><td>Kelas 7 SMP</td><td>Semester 1</td><td>1 Juz (Juz 30)</td><td><strong>1 Juz</strong></td></tr>
          <tr><td>Kelas 7 SMP</td><td>Semester 2</td><td>1 Juz (Juz 29)</td><td><strong>2 Juz</strong></td></tr>
          <tr style="background:#e6f4ef"><td>Kelas 8 SMP ★</td><td>Semester 1</td><td>1/2 Juz (Juz 28)</td><td><strong>2.5 Juz</strong></td></tr>
          <tr><td>Kelas 8 SMP</td><td>Semester 2</td><td>1/2 Juz (Juz 28)</td><td><strong>3 Juz</strong></td></tr>
          <tr><td>Kelas 9 SMP</td><td>Semester 1–2</td><td>1 Juz (Juz 27)</td><td><strong>4 Juz</strong></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>"""
    return shell(body, f"Laporan — {a['nama']}")


def page_ganti_password() -> str:
    body = f"""
<div class="panel" style="max-width:480px">
  <div class="panel-header"><h2>Ganti Password</h2></div>
  <div class="panel-body">
    <p style="margin-top:0;color:var(--muted);font-size:0.9rem">
      Username Anda: <strong>{SAMPLE['nama_ortu']}</strong><br>
      Untuk orang tua, username adalah nama orang tua sesuai data sekolah.
    </p>
    <form>
      <div style="margin-bottom:0.9rem"><label>Password saat ini</label><input type="password"></div>
      <div style="margin-bottom:0.9rem"><label>Password baru (min. 6 karakter)</label><input type="password"></div>
      <div style="margin-bottom:1rem"><label>Ulangi password baru</label><input type="password"></div>
      <div class="form-actions">
        <button class="btn btn-primary" type="button">Simpan Password</button>
        <a class="btn btn-ghost" href="#">Batal</a>
      </div>
    </form>
  </div>
</div>"""
    return shell(body, "Ganti Password")


PAGES = [
    ("01_login_ortu", "Login Orang Tua", page_login),
    ("02_dashboard_ortu", "Dashboard — Perkembangan Anak", page_dashboard),
    ("03_laporan_index_ortu", "Menu Laporan Lengkap", page_laporan_index),
    ("04_laporan_detail_ortu", "Laporan Detail Anak (Realtime)", page_laporan_detail),
    ("05_ganti_password_ortu", "Ganti Password Orang Tua", page_ganti_password),
]


def capture():
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    html_dir = SHOT_DIR / "html"
    html_dir.mkdir(exist_ok=True)
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            device_scale_factor=1.25,
        )
        page = context.new_page()
        for slug, title, builder in PAGES:
            html_path = html_dir / f"{slug}.html"
            html_path.write_text(builder(), encoding="utf-8")
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(300)
            out = SHOT_DIR / f"{slug}.png"
            page.screenshot(path=str(out), full_page=True)
            files.append((title, out))
            print(f"✓ {title}")
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

    c.setFillColorRGB(0.04, 0.24, 0.18)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h / 2 + 48, "Tampilan Menu & Laporan")
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h / 2 + 22, "Portal Orang Tua")
    c.setFont("Helvetica", 11)
    c.drawCentredString(page_w / 2, page_h / 2 - 8, "Laporan Hasil Belajar Tahfidz Realtime")
    c.drawCentredString(page_w / 2, page_h / 2 - 28, SAMPLE["school_name"])
    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, 28 * mm, "Katalog antarmuka khusus akun orang tua murid")
    c.showPage()

    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.04, 0.24, 0.18)
    c.drawString(margin, page_h - 25 * mm, "Daftar Tampilan Orang Tua")
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.1, 0.18, 0.16)
    y = page_h - 40 * mm
    for i, (title, _) in enumerate(files, 1):
        c.drawString(margin, y, f"{i}. {title}")
        y -= 9 * mm
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.35, 0.45, 0.4)
    c.drawString(margin, y - 8 * mm, "Catatan: orang tua hanya dapat melihat data anaknya sendiri secara realtime.")
    c.showPage()

    for i, (title, path) in enumerate(files, 1):
        c.setFillColorRGB(0.04, 0.24, 0.18)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, page_h - 16 * mm, f"{i}. {title}")
        max_w = page_w - 2 * margin
        max_h = page_h - 30 * mm
        disp_w, disp_h, im = fit_image(path, max_w, max_h)
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
        y = page_h - 22 * mm - disp_h
        c.drawImage(ImageReader(buf), x, y, width=disp_w, height=disp_h)
        c.showPage()
        print(f"PDF: {title}")

    c.save()
    print(f"\nPDF siap: {PDF_PATH}")


if __name__ == "__main__":
    shots = capture()
    build_pdf(shots)
