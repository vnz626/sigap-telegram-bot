-- Skema Database SIGAP (MySQL / MariaDB XAMPP)
-- Jalankan lewat tab SQL di http://localhost/phpmyadmin

CREATE DATABASE IF NOT EXISTS sigap
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sigap;

CREATE TABLE IF NOT EXISTS log_keputusan (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  waktu         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sesi_id       CHAR(32) NOT NULL,
  intent        VARCHAR(40) NULL,
  confidence    DECIMAL(4,3) NULL,
  entity_json   JSON NULL,
  aksi          VARCHAR(20) NOT NULL,
  id_respons    VARCHAR(20) NULL,
  versi_kb      VARCHAR(20) NOT NULL,
  latensi_ms    INT NULL,
  INDEX idx_waktu (waktu),
  INDEX idx_aksi (aksi)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ucapan_tidak_dikenali (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  waktu            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  teks_dimasking   VARCHAR(500) NOT NULL,
  kandidat_teratas VARCHAR(40) NULL,
  confidence       DECIMAL(4,3) NULL,
  status_tinjau    ENUM('baru','dipakai','diabaikan') NOT NULL DEFAULT 'baru',
  INDEX idx_status (status_tinjau)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feedback (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  waktu       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sesi_id     CHAR(32) NOT NULL,
  id_respons  VARCHAR(20) NOT NULL,
  nilai       TINYINT NOT NULL,          -- 1 = membantu, -1 = tidak
  versi_kb    VARCHAR(20) NOT NULL,
  INDEX idx_respons (id_respons)
) ENGINE=InnoDB;

