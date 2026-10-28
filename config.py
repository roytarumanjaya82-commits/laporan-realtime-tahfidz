import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "smpm22-tahfidz-secret-key-ubah-di-produksi")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "tahfidz_smpm22")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    BLANKO_FOLDER = os.path.join(os.path.dirname(__file__), "blanko")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
    SCHOOL_NAME = "SMP Muhammadiyah 22 Setiabudi Pamulang"
    APP_TITLE = "Laporan Hasil Belajar Tahfidz Realtime"
    TARGET_TOTAL_JUZ = 4.0
    # Password default orang tua (fallback jika belum ada di app_settings)
    PARENT_DEFAULT_PASSWORD = os.getenv("PARENT_DEFAULT_PASSWORD", "ortuSMPM22")