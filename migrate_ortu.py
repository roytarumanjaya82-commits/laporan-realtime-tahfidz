"""Migrasi: akun orang tua + relasi ke siswa."""

import sys

import pymysql
from werkzeug.security import generate_password_hash

from config import Config

DEFAULT_PASSWORD = "ortuSMPM22"

STATEMENTS = [
    # Perpanjang username & tambah role orang_tua
    """
    ALTER TABLE users
      MODIFY username VARCHAR(120) NOT NULL,
      MODIFY role ENUM('admin','musyrif','orang_tua') NOT NULL DEFAULT 'musyrif'
    """,
    # Flag password default (belum diganti orang tua)
    """
    ALTER TABLE users
      ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0
      AFTER aktif
    """,
    # Relasi siswa → user orang tua
    """
    ALTER TABLE siswa
      ADD COLUMN orang_tua_user_id INT DEFAULT NULL AFTER musyrif_id
    """,
    """
    ALTER TABLE siswa
      ADD CONSTRAINT fk_siswa_ortu
      FOREIGN KEY (orang_tua_user_id) REFERENCES users(id) ON DELETE SET NULL
    """,
    # Settings aplikasi (password default ortu, dll.)
    """
    CREATE TABLE IF NOT EXISTS app_settings (
      setting_key VARCHAR(64) PRIMARY KEY,
      setting_value TEXT NOT NULL,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB
    """,
]


def column_exists(cur, table, column):
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (Config.MYSQL_DB, table, column),
    )
    return cur.fetchone()[0] > 0


def constraint_exists(cur, name):
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA=%s AND CONSTRAINT_NAME=%s
        """,
        (Config.MYSQL_DB, name),
    )
    return cur.fetchone()[0] > 0


def run():
    conn = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            # users.username + role
            cur.execute(
                """
                ALTER TABLE users
                  MODIFY username VARCHAR(120) NOT NULL,
                  MODIFY role ENUM('admin','musyrif','orang_tua') NOT NULL DEFAULT 'musyrif'
                """
            )
            print("✓ users.username & role diperbarui")

            if not column_exists(cur, "users", "must_change_password"):
                cur.execute(
                    "ALTER TABLE users ADD COLUMN must_change_password TINYINT(1) "
                    "NOT NULL DEFAULT 0 AFTER aktif"
                )
                print("✓ kolom must_change_password ditambahkan")
            else:
                print("• must_change_password sudah ada")

            if not column_exists(cur, "siswa", "orang_tua_user_id"):
                cur.execute(
                    "ALTER TABLE siswa ADD COLUMN orang_tua_user_id INT DEFAULT NULL AFTER musyrif_id"
                )
                print("✓ kolom siswa.orang_tua_user_id ditambahkan")
            else:
                print("• orang_tua_user_id sudah ada")

            if not constraint_exists(cur, "fk_siswa_ortu"):
                try:
                    cur.execute(
                        "ALTER TABLE siswa ADD CONSTRAINT fk_siswa_ortu "
                        "FOREIGN KEY (orang_tua_user_id) REFERENCES users(id) ON DELETE SET NULL"
                    )
                    print("✓ FK fk_siswa_ortu ditambahkan")
                except Exception as e:
                    print(f"• FK dilewati: {e}")
            else:
                print("• FK fk_siswa_ortu sudah ada")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                  setting_key VARCHAR(64) PRIMARY KEY,
                  setting_value TEXT NOT NULL,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """
            )
            print("✓ tabel app_settings siap")

            cur.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key=%s",
                ("parent_default_password",),
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)",
                    ("parent_default_password", DEFAULT_PASSWORD),
                )
                print(f"✓ password default orang tua diset: {DEFAULT_PASSWORD}")
            else:
                print("• password default orang tua sudah ada")

    finally:
        conn.close()
    print("Migrasi selesai.")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Gagal migrasi: {e}", file=sys.stderr)
        sys.exit(1)