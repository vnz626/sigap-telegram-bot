"""Manajemen koneksi PyMySQL ke MySQL XAMPP dengan mode tahan-gagal (fail-safe)."""

import pymysql
from pymysql.cursors import DictCursor
import config


def buat_koneksi():
    """Membuat koneksi baru ke MySQL XAMPP sesuai konfigurasi .env."""
    return pymysql.connect(
        host=config.DB["host"],
        port=config.DB["port"],
        user=config.DB["user"],
        password=config.DB["password"],
        database=config.DB["database"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=2,
        read_timeout=3,
        write_timeout=3,
        autocommit=False,
    )


def cek_status_db() -> str:
    """Memeriksa ketersediaan database MySQL untuk endpoint /health."""
    conn = None
    try:
        conn = buat_koneksi()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return "tersedia"
    except Exception:
        return "tidak tersedia"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

