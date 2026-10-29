-- Database: Laporan Hasil Belajar Tahfidz Realtime
-- SMP Muhammadiyah 22 Setiabudi Pamulang — Jenjang 7–9

CREATE DATABASE IF NOT EXISTS tahfidz_smpm22
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE tahfidz_smpm22;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  nama_lengkap VARCHAR(120) NOT NULL,
  role ENUM('admin','musyrif','orang_tua') NOT NULL DEFAULT 'musyrif',
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  must_change_password TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_settings (
  setting_key VARCHAR(64) PRIMARY KEY,
  setting_value TEXT NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tahun_ajaran (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nama VARCHAR(20) NOT NULL UNIQUE,          -- contoh: 2026/2027
  semester ENUM('1','2') NOT NULL DEFAULT '1',
  aktif TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS musyrif (
  id INT AUTO_INCREMENT PRIMARY KEY,
  kode VARCHAR(20) NOT NULL,
  nama VARCHAR(120) NOT NULL,
  gelar VARCHAR(60) DEFAULT NULL,
  telepon VARCHAR(30) DEFAULT NULL,
  user_id INT DEFAULT NULL,
  tahun_ajaran_id INT NOT NULL,
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_musyrif_kode_ta (kode, tahun_ajaran_id),
  CONSTRAINT fk_musyrif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_musyrif_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS kelas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nama VARCHAR(30) NOT NULL,                 -- contoh: 7-A, 8-B
  jenjang TINYINT NOT NULL,                  -- 7, 8, atau 9
  tahun_ajaran_id INT NOT NULL,
  musyrif_id INT DEFAULT NULL,
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_kelas_nama_ta (nama, tahun_ajaran_id),
  CONSTRAINT fk_kelas_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_kelas_musyrif FOREIGN KEY (musyrif_id) REFERENCES musyrif(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS siswa (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nis VARCHAR(30) NOT NULL,
  nama VARCHAR(120) NOT NULL,
  jenis_kelamin ENUM('L','P') NOT NULL DEFAULT 'L',
  kelas_id INT NOT NULL,
  musyrif_id INT DEFAULT NULL,
  orang_tua_user_id INT DEFAULT NULL,
  tahun_ajaran_id INT NOT NULL,
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_siswa_nis_ta (nis, tahun_ajaran_id),
  CONSTRAINT fk_siswa_kelas FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE RESTRICT,
  CONSTRAINT fk_siswa_musyrif FOREIGN KEY (musyrif_id) REFERENCES musyrif(id) ON DELETE SET NULL,
  CONSTRAINT fk_siswa_ortu FOREIGN KEY (orang_tua_user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_siswa_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS setoran (
  id INT AUTO_INCREMENT PRIMARY KEY,
  siswa_id INT NOT NULL,
  tahun_ajaran_id INT NOT NULL,
  tanggal DATETIME NOT NULL,
  jenis ENUM('Ziyadah','Muraja''ah') NOT NULL,
  surah VARCHAR(120) NOT NULL,
  ayat_awal INT DEFAULT NULL,
  ayat_akhir INT DEFAULT NULL,
  juz DECIMAL(4,1) DEFAULT NULL,
  volume_halaman DECIMAL(6,2) NOT NULL DEFAULT 0,
  volume_baris DECIMAL(6,2) NOT NULL DEFAULT 0,
  nilai INT NOT NULL DEFAULT 0,
  predikat VARCHAR(40) DEFAULT NULL,
  status ENUM('Lulus','Ulang') NOT NULL DEFAULT 'Lulus',
  catatan TEXT,
  musyrif_id INT DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_setoran_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE,
  CONSTRAINT fk_setoran_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_setoran_musyrif FOREIGN KEY (musyrif_id) REFERENCES musyrif(id) ON DELETE SET NULL,
  INDEX idx_setoran_siswa_tgl (siswa_id, tanggal),
  INDEX idx_setoran_ta (tahun_ajaran_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS evaluasi (
  id INT AUTO_INCREMENT PRIMARY KEY,
  siswa_id INT NOT NULL,
  tahun_ajaran_id INT NOT NULL,
  kelancaran INT NOT NULL DEFAULT 0,
  tajwid INT NOT NULL DEFAULT 0,
  makharijul INT NOT NULL DEFAULT 0,
  adab INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_evaluasi_siswa_ta (siswa_id, tahun_ajaran_id),
  CONSTRAINT fk_evaluasi_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE,
  CONSTRAINT fk_evaluasi_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Seed admin default (password: admin123) — hash diisi oleh init_db.py
INSERT INTO tahun_ajaran (nama, semester, aktif)
VALUES ('2026/2027', '1', 1)
ON DUPLICATE KEY UPDATE aktif = VALUES(aktif);

INSERT INTO app_settings (setting_key, setting_value)
VALUES ('parent_default_password', 'ortuSMPM22')
ON DUPLICATE KEY UPDATE setting_key = setting_key;