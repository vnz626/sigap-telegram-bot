"""Konfigurasi aplikasi SIGAP (membaca variabel lingkungan dari .env)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
_ENV_FILE = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE)
except ImportError:
    if _ENV_FILE.is_file():
        for _baris in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            _b = _baris.strip()
            if _b and not _b.startswith("#") and "=" in _b:
                _k, _v = _b.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

SECRET_KEY = os.getenv("SECRET_KEY", "sigap-dev-secret-key-lokal-jangan-dipakai-publik")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

DEBUG_PANEL = os.getenv("DEBUG_PANEL", "true").strip().lower() in ("1", "true", "yes", "on")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

_kb_env = os.getenv("KB_PATH", "kb")
KB_PATH = str((BASE_DIR / _kb_env).resolve()) if not os.path.isabs(_kb_env) else _kb_env

DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "sigap"),
}

NLU = {
    "bobot_kuat": 3,
    "bobot_pendukung": 1,
    "skor_penuh": 6,
    "ambang_confidence": 0.5,
    "ambang_selisih_ambigu": 0.15,
    "ambang_fuzzy": 0.85,
    "fuzzy_min_panjang_kata": 4,
}

SESI = {
    "ttl_detik": 600,
    "klarifikasi_timeout_detik": 300,
    "fallback_sebelum_menu": 2,
}

BATAS = {
    "panjang_pesan_maks": 1000,
    "pesan_per_menit": 20,
}

