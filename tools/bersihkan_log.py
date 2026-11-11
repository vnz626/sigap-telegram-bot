"""Skrip CLI pemeliharaan untuk membersihkan log lama di database MySQL XAMPP (Bagian 11)."""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.koneksi import buat_koneksi


def bersihkan(hari: int = 30) -> int:
    conn = None
    try:
        conn = buat_koneksi()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM log_keputusan WHERE waktu < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (int(hari),),
            )
            jml_log = cur.rowcount
            cur.execute(
                "DELETE FROM ucapan_tidak_dikenali WHERE status_tinjau != 'baru' AND waktu < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (int(hari),),
            )
            jml_ucapan = cur.rowcount
        conn.commit()
        print(f"[OK] Pembersihan selesai: {jml_log} baris log_keputusan dan {jml_ucapan} baris ucapan_tidak_dikenali (> {hari} hari) dihapus.")
        return 0
    except Exception as exc:
        print(f"[PERINGATAN] Gagal membersihkan log MySQL (pastikan MySQL XAMPP menyala): {exc}")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bersihkan log SIGAP yang lebih tua dari N hari.")
    parser.add_argument("--hari", type=int, default=30, help="Batas retensi hari (bawaan: 30)")
    args = parser.parse_args()
    sys.exit(bersihkan(args.hari))

