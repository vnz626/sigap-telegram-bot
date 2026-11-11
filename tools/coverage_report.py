"""Skrip CLI untuk menampilkan matriks cakupan Bencana × Fase/Intent pada Knowledge Base SIGAP."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from kb_loader import muat_kb

FASE_KOLOM = [
    ("info_sebelum", "Sebelum"),
    ("info_saat", "Saat"),
    ("info_sesudah", "Sesudah"),
    ("tanda_peringatan", "Tanda"),
    ("penyebab", "Penyebab"),
]


def cetak_laporan() -> int:
    kb = muat_kb(config.KB_PATH)
    bencana_map = kb.entities.get("bencana", {})

    print("=" * 78)
    print(f"LAPORAN CAKUPAN MATRIKS KNOWLEDGE BASE SIGAP (Versi {kb.versi})")
    print("=" * 78)
    header = f"{'Bencana':<22} | {'Prio':<4} | " + " | ".join(f"{label:<8}" for _, label in FASE_KOLOM)
    print(header)
    print("-" * 78)

    p1_bolong = 0
    for kode_b, info in bencana_map.items():
        prio = info.get("prioritas", 2)
        sel = []
        for it_tag, _ in FASE_KOLOM:
            resp = kb.ambil_respons(it_tag, {"bencana": kode_b})
            if resp and resp.get("entity", {}).get("bencana") == kode_b:
                sel.append(f"{resp['id']:<8}")
            else:
                sel.append(f"{'-':<8}")
                if prio == 1 and it_tag in ("info_sebelum", "info_saat", "info_sesudah"):
                    p1_bolong += 1
        print(f"{kode_b:<22} | P{prio:<3} | " + " | ".join(sel))

    print("-" * 78)
    if p1_bolong > 0:
        print(f"[GAGAL] Terdapat {p1_bolong} sel matriks wajib P1 yang masih kosong.")
        return 1

    print("[OK] Seluruh matriks wajib Bencana P1 × Fase P1 terisi penuh (100%).")
    return 0


if __name__ == "__main__":
    sys.exit(cetak_laporan())

