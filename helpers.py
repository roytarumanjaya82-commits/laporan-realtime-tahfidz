"""Logika target hafalan & predikat sesuai dokumen V2."""

from config import Config

# Target kumulatif (juz) di akhir tiap periode
TARGET_MAP = {
    (7, 1): {"ziyadah": "1 Juz (Juz 30) + Tahsin/Tajwid", "kumulatif": 1.0},
    (7, 2): {"ziyadah": "1 Juz (Juz 29)", "kumulatif": 2.0},
    (8, 1): {"ziyadah": "1/2 Juz (Juz 28: Al-Mujadila s.d. Al-Saff)", "kumulatif": 2.5},
    (8, 2): {"ziyadah": "1/2 Juz (Juz 28: Al-Jumu'ah s.d. At-Tahrim)", "kumulatif": 3.0},
    (9, 1): {"ziyadah": "1/2 Juz (Juz 27: Adz-Dzariyat s.d. An-Najm)", "kumulatif": 3.5},
    (9, 2): {"ziyadah": "1/2 Juz (Juz 27: Al-Qamar s.d. Al-Waqi'ah) + Muraja'ah Agung", "kumulatif": 4.0},
}

HALAMAN_PER_JUZ = 20.0  # perkiraan standar untuk konversi halaman → juz


def predikat_dari_nilai(nilai: int) -> str:
    if nilai >= 90:
        return "Sangat Baik"
    if nilai >= 80:
        return "Baik"
    if nilai >= 70:
        return "Cukup"
    return "Perlu Bimbingan"


def predikat_huruf(nilai: int) -> str:
    if nilai >= 90:
        return "A"
    if nilai >= 80:
        return "B"
    if nilai >= 70:
        return "C"
    return "D"


def target_periode(jenjang: int, semester: int | str) -> dict:
    sem = int(semester)
    return TARGET_MAP.get((jenjang, sem), {"ziyadah": "-", "kumulatif": Config.TARGET_TOTAL_JUZ})


def halaman_ke_juz(halaman: float) -> float:
    return round(float(halaman or 0) / HALAMAN_PER_JUZ, 3)


def format_capaian(total_halaman: float) -> str:
    total = float(total_halaman or 0)
    juz = int(total // HALAMAN_PER_JUZ)
    sisa = round(total % HALAMAN_PER_JUZ, 1)
    if juz == 0:
        return f"{sisa} Halaman"
    if sisa == 0:
        return f"{juz} Juz"
    return f"{juz} Juz + {sisa} Halaman"


def status_on_track(capaian_juz: float, target_kumulatif: float, toleransi: float = 0.15) -> dict:
    if target_kumulatif <= 0:
        return {"kode": "unknown", "label": "Belum Ada Target", "warna": "muted"}
    rasio = capaian_juz / target_kumulatif
    if rasio >= 1.0:
        return {"kode": "ahead", "label": "Melebihi Target", "warna": "success"}
    if rasio >= (1.0 - toleransi):
        return {"kode": "ontrack", "label": "On Track", "warna": "success"}
    if rasio >= 0.6:
        return {"kode": "watch", "label": "Perlu Perhatian", "warna": "warning"}
    return {"kode": "behind", "label": "Tertinggal", "warna": "danger"}


def hitung_progress(total_halaman: float, jenjang: int, semester: int | str) -> dict:
    total = float(total_halaman or 0)
    capaian_juz = halaman_ke_juz(total)
    target = target_periode(jenjang, semester)
    target_kum = target["kumulatif"]
    target_total = Config.TARGET_TOTAL_JUZ
    persen_periode = round(min(capaian_juz / target_kum * 100, 100), 1) if target_kum else 0
    persen_lulus = round(min(capaian_juz / target_total * 100, 100), 1) if target_total else 0
    status = status_on_track(capaian_juz, target_kum)
    return {
        "total_halaman": round(total, 2),
        "capaian_juz": capaian_juz,
        "capaian_teks": format_capaian(total_halaman),
        "target_kumulatif": target_kum,
        "target_ziyadah": target["ziyadah"],
        "target_total": target_total,
        "persen_periode": persen_periode,
        "persen_lulus": persen_lulus,
        "status": status,
    }