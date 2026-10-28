"""Inisialisasi database: jalankan schema.sql + buat user admin default."""

import os
import sys

import pymysql
from werkzeug.security import generate_password_hash

from config import Config


def run():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        schema = f.read()

    # Koneksi tanpa database dulu untuk CREATE DATABASE
    conn = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            for statement in schema.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        print("✓ Schema berhasil dijalankan.")
    finally:
        conn.close()

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
            cur.execute("SELECT id FROM users WHERE username=%s", ("admin",))
            if not cur.fetchone():
                pw = generate_password_hash("admin123")
                cur.execute(
                    "INSERT INTO users (username, password_hash, nama_lengkap, role) "
                    "VALUES (%s, %s, %s, %s)",
                    ("admin", pw, "Administrator Tahfidz", "admin"),
                )
                print("✓ User admin dibuat (username: admin / password: admin123)")
            else:
                print("• User admin sudah ada, dilewati.")
    finally:
        conn.close()

    print("Selesai. Jalankan: python app.py")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Gagal inisialisasi DB: {e}", file=sys.stderr)
        sys.exit(1)