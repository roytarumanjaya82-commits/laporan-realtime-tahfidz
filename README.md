# Laporan Hasil Belajar Tahfidz Realtime

Aplikasi web laporan hasil belajar Tahfidz Al-Qur'an **realtime** untuk jenjang **7–9** di **SMP Muhammadiyah 22 Setiabudi Pamulang**.

Dibangun dengan **Python · Flask · MySQL**, mengikuti skema target dokumen *Laporan Hasil Belajar Tahfidz Murid SMP Realtime V2* (total lulus **4 Juz**).

## Fitur

- Dashboard progress per kelas & log setoran terbaru
- Input setoran harian (Ziyadah / Muraja'ah) dengan kalkulasi otomatis
- Laporan murid: identitas, capaian, % target, evaluasi kualitas, skema target
- Data master terikat **tahun ajaran**: siswa, kelas, musyrif
- **Blanko Excel gabungan** (satu file/satu tabel): musyrif + kelas + siswa
- Admin dapat **memindahkan siswa antar musyrif**
- Multi user (admin, musyrif, orang tua)

## Target Hafalan (V2)

| Tingkat | Periode | Target Ziyadah | Kumulatif |
|---------|---------|----------------|-----------|
| Kelas 7 | Sem 1 | 1 Juz (Juz 30) | 1 Juz |
| Kelas 7 | Sem 2 | 1 Juz (Juz 29) | 2 Juz |
| Kelas 8 | Sem 1 | 1/2 Juz (Juz 28) | 2,5 Juz |
| Kelas 8 | Sem 2 | 1/2 Juz (Juz 28) | 3 Juz |
| Kelas 9 | Sem 1 | 1/2 Juz (Juz 27) | 3,5 Juz |
| Kelas 9 | Sem 2 | 1/2 Juz (Juz 27) + Muraja'ah | **4 Juz** |

## Persyaratan

- Python 3.10+
- MySQL 5.7+ / MariaDB 10.3+
- pip

## Instalasi

```bash
cd "d:\ROY\KELAS TAHFIDZ\LAPORAN REALTIME TAHFIDZ"

python -m venv venv
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
```

Salin konfigurasi database:

```bash
copy .env.example .env
```

Edit `.env` sesuai kredensial MySQL Anda:

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password_anda
MYSQL_DB=tahfidz_smpm22
```

Inisialisasi database & user admin:

```bash
python init_db.py
```

Jalankan aplikasi:

```bash
python app.py
```

Buka: [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Login default staf:** `admin` / `admin123` — segera ganti setelah pertama kali masuk.

**Login orang tua:** username = **nama orang tua** (sesuai data siswa), password awal default sistem = `ortuSMPM22` (bisa diubah & direset oleh admin di menu **Akun Orang Tua**). Orang tua dapat mengganti password sendiri dan melihat perkembangan anak secara realtime.

Jika database sudah pernah dibuat sebelumnya, jalankan migrasi:

```bash
python migrate_ortu.py
```

## Alur Penggunaan

1. Login sebagai admin → pastikan tahun ajaran aktif (default `2026/2027`).
2. Menu **Blanko Unduh/Upload** → unduh satu file Excel gabungan, isi, lalu upload sekali (musyrif + kelas + siswa + nama ortu).
3. Admin dapat memindahkan siswa antar musyrif lewat menu **Pindah Musyrif**.
4. Musyrif / admin input **Setoran Realtime** saat murid menyetor.
5. Buka **Laporan Murid** untuk melihat progress & cetak laporan.
6. Orang tua login dengan namanya → dashboard perkembangan anak & laporan lengkap (hanya anaknya).

## Struktur Folder

```
├── app.py              # Aplikasi Flask (routes)
├── blanko_service.py   # Generate & parse Excel
├── helpers.py          # Kalkulasi target & predikat
├── db.py               # Koneksi MySQL
├── config.py / .env
├── schema.sql
├── init_db.py
├── templates/
├── static/css/
├── blanko/             # File blanko tersimpan
└── uploads/
```

## Catatan

- Progress Ziyadah dihitung dari volume halaman setoran berstatus **Lulus** (≈ 20 halaman = 1 Juz).
- Evaluasi kualitas bisa diisi manual di halaman laporan, atau tersinkron otomatis dari rata-rata nilai setoran.
- Ganti `SECRET_KEY` di `.env` sebelum dipakai di produksi.