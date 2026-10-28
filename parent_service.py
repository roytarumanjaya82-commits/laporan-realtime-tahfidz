"""Layanan akun orang tua: password default, buat/cari akun, reset."""

from werkzeug.security import generate_password_hash

from db import execute, query_one

DEFAULT_FALLBACK = "ortuSMPM22"


def get_default_parent_password() -> str:
    row = query_one(
        "SELECT setting_value FROM app_settings WHERE setting_key=%s",
        ("parent_default_password",),
    )
    return (row["setting_value"] if row else DEFAULT_FALLBACK).strip() or DEFAULT_FALLBACK


def set_default_parent_password(password: str):
    password = password.strip()
    if not password:
        raise ValueError("Password default tidak boleh kosong")
    existing = query_one(
        "SELECT setting_key FROM app_settings WHERE setting_key=%s",
        ("parent_default_password",),
    )
    if existing:
        execute(
            "UPDATE app_settings SET setting_value=%s WHERE setting_key=%s",
            (password, "parent_default_password"),
        )
    else:
        execute(
            "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)",
            ("parent_default_password", password),
        )


def normalize_parent_username(nama: str) -> str:
    """Username login = nama orang tua (trim, spasi ganda dirapikan)."""
    return " ".join((nama or "").strip().split())


def ensure_parent_account(nama_orang_tua: str, telepon: str | None = None) -> int | None:
    """
    Cari atau buat akun role orang_tua.
    Username = nama orang tua. Password awal = default sistem.
    Return user_id atau None jika nama kosong.
    """
    username = normalize_parent_username(nama_orang_tua)
    if not username:
        return None

    existing = query_one(
        "SELECT id, role FROM users WHERE LOWER(username)=LOWER(%s)",
        (username,),
    )
    if existing:
        if existing["role"] != "orang_tua":
            raise ValueError(
                f"Username '{username}' sudah dipakai akun {existing['role']}. "
                "Gunakan nama orang tua yang berbeda."
            )
        # aktifkan kembali jika nonaktif
        execute("UPDATE users SET aktif=1 WHERE id=%s", (existing["id"],))
        return existing["id"]

    pw = get_default_parent_password()
    user_id = execute(
        "INSERT INTO users (username, password_hash, nama_lengkap, role, must_change_password) "
        "VALUES (%s,%s,%s,'orang_tua',1)",
        (username, generate_password_hash(pw), username),
    )
    return user_id


def reset_parent_password(user_id: int, password: str | None = None):
    """Reset password orang tua ke default (atau password yang diberikan)."""
    pw = (password or get_default_parent_password()).strip()
    execute(
        "UPDATE users SET password_hash=%s, must_change_password=1, aktif=1 WHERE id=%s AND role='orang_tua'",
        (generate_password_hash(pw), user_id),
    )


def reset_all_parent_passwords_to_default():
    pw = get_default_parent_password()
    hashed = generate_password_hash(pw)
    execute(
        "UPDATE users SET password_hash=%s, must_change_password=1 WHERE role='orang_tua' AND aktif=1",
        (hashed,),
    )


def get_children_of_parent(user_id: int, tahun_ajaran_id: int | None = None):
    from db import query_all

    sql = """
        SELECT s.*, k.nama AS nama_kelas, k.jenjang, m.nama AS nama_musyrif
        FROM siswa s
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = COALESCE(s.musyrif_id, k.musyrif_id)
        WHERE s.orang_tua_user_id=%s AND s.aktif=1
    """
    params = [user_id]
    if tahun_ajaran_id:
        sql += " AND s.tahun_ajaran_id=%s"
        params.append(tahun_ajaran_id)
    sql += " ORDER BY k.jenjang, k.nama, s.nama"
    return query_all(sql, params)


def parent_owns_siswa(user_id: int, siswa_id: int) -> bool:
    row = query_one(
        "SELECT id FROM siswa WHERE id=%s AND orang_tua_user_id=%s AND aktif=1",
        (siswa_id, user_id),
    )
    return bool(row)