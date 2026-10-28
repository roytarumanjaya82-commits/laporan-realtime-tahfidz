"""Seed contoh akun orang tua + siswa untuk uji login."""

from db import execute, query_one
from parent_service import ensure_parent_account, get_default_parent_password


def main():
    ta = query_one("SELECT * FROM tahun_ajaran WHERE aktif=1")
    if not ta:
        raise SystemExit("Tidak ada tahun ajaran aktif")

    kelas = query_one(
        "SELECT * FROM kelas WHERE tahun_ajaran_id=%s LIMIT 1", (ta["id"],)
    )
    if not kelas:
        execute(
            "INSERT INTO kelas (nama, jenjang, tahun_ajaran_id) VALUES (%s,%s,%s)",
            ("8-A", 8, ta["id"]),
        )
        kelas = query_one(
            "SELECT * FROM kelas WHERE nama=%s AND tahun_ajaran_id=%s",
            ("8-A", ta["id"]),
        )
        print("Kelas 8-A dibuat")

    ortu_id = ensure_parent_account("Budi Santoso", "081234567890")
    print("Orang tua user_id:", ortu_id)

    siswa = query_one(
        "SELECT * FROM siswa WHERE nis=%s AND tahun_ajaran_id=%s",
        ("2507001", ta["id"]),
    )
    if not siswa:
        execute(
            "INSERT INTO siswa (nis, nama, jenis_kelamin, kelas_id, orang_tua_user_id, tahun_ajaran_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("2507001", "Ahmad Fauzan", "L", kelas["id"], ortu_id, ta["id"]),
        )
        print("Siswa Ahmad Fauzan dibuat")
    else:
        execute(
            "UPDATE siswa SET orang_tua_user_id=%s WHERE id=%s",
            (ortu_id, siswa["id"]),
        )
        print("Siswa dihubungkan ke orang tua")

    print(f"Login ortu: username 'Budi Santoso' / password '{get_default_parent_password()}'")


if __name__ == "__main__":
    main()