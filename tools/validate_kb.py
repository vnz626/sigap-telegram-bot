"""Skrip CLI untuk memvalidasi integritas dan aturan keselamatan Knowledge Base SIGAP (Bagian 7.3)."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from kb_loader import BERKAS_WAJIB, validasi_data_kb


def jalankan_validasi(kb_dir: str | Path | None = None) -> int:
    jalur = Path(kb_dir or config.KB_PATH)
    print(f"[SIGAP] Memvalidasi Knowledge Base di: {jalur}")

    raw_files = {}
    for nama in BERKAS_WAJIB:
        berkas = jalur / nama
        if not berkas.is_file():
            print(f"[ERROR] Berkas wajib tidak ditemukan: {berkas}")
            return 1
        try:
            with open(berkas, "r", encoding="utf-8") as f:
                raw_files[nama] = json.load(f)
        except Exception as exc:
            print(f"[ERROR] Gagal mengurai JSON pada '{nama}': {exc}")
            return 1

    errors, warnings = validasi_data_kb(raw_files)

    for w in warnings:
        print(f"[PERINGATAN] {w}")

    if errors:
        print(f"\n[GAGAL] Ditemukan {len(errors)} kesalahan validasi KB:")
        for err in errors:
            print(f"  - {err}")
        return 1

    jml_intent = len(raw_files["intents.json"].get("intents", []))
    jml_resp = len(raw_files["responses.json"].get("responses", []))
    jml_glos = len(raw_files["glossary.json"].get("istilah", {}))
    print(
        f"[OK] Knowledge Base valid dan bersih! "
        f"({jml_intent} intent, {jml_resp} respons, {jml_glos} istilah glosarium, {len(warnings)} peringatan)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(jalankan_validasi())

