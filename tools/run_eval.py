"""Skrip CLI evaluasi regresi NLU SIGAP terhadap bank uji tests/test_cases.json."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from kb_loader import muat_kb
from core.engine import Core
from core.model import PesanMasuk, Sesi


def jalankan_evaluasi() -> int:
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    berkas_uji = ROOT_DIR / "tests" / "test_cases.json"
    with open(berkas_uji, "r", encoding="utf-8") as f:
        data_uji = json.load(f)

    kasus_list = data_uji.get("cases", [])
    if not kasus_list:
        print("[ERROR] Bank uji kosong.")
        return 1

    total = len(kasus_list)
    benar_intent = 0
    benar_entity = 0
    total_darurat = 0
    benar_darurat = 0
    gagal_detail = []

    for idx, k in enumerate(kasus_list, start=1):
        teks = k["teks"]
        exp_intent = k.get("intent")
        exp_aksi = k.get("aksi")
        exp_entity = k.get("entity", {})
        exp_darurat = bool(k.get("darurat", exp_intent == "darurat_aktif"))

        balasan, _, keputusan = core.proses(PesanMasuk(teks=teks, waktu_epoch=1000.0), Sesi())
        aktual_intent = keputusan.nlu.terpilih.tag if keputusan.nlu.terpilih else None
        aktual_entity = keputusan.nlu.entity

        # Evaluasi darurat
        if exp_darurat:
            total_darurat += 1
            if keputusan.aksi == "darurat" and balasan.darurat:
                benar_darurat += 1

        # Evaluasi intent / aksi
        cocok_it = True
        if exp_intent is not None and aktual_intent != exp_intent:
            cocok_it = False
        if exp_aksi is not None and keputusan.aksi != exp_aksi:
            cocok_it = False

        if cocok_it:
            benar_intent += 1

        # Evaluasi entity wajib yang diharapkan pada kasus uji
        cocok_ent = all(aktual_entity.get(ek) == ev for ek, ev in exp_entity.items())
        if cocok_ent:
            benar_entity += 1

        if not (cocok_it and cocok_ent):
            gagal_detail.append(
                f"  #{idx} '{teks}' -> dapat intent={aktual_intent}, aksi={keputusan.aksi}, entity={aktual_entity} "
                f"(target: intent={exp_intent}, aksi={exp_aksi}, entity={exp_entity})"
            )

    akurasi_intent = (benar_intent / total) * 100.0
    akurasi_entity = (benar_entity / total) * 100.0
    akurasi_darurat = (benar_darurat / total_darurat) * 100.0 if total_darurat > 0 else 100.0

    print("=" * 72)
    print("HASIL EVALUASI NLU SIGAP (tests/test_cases.json)")
    print("=" * 72)
    print(f"Total kasus uji        : {total}")
    print(f"Akurasi Intent/Aksi    : {benar_intent}/{total} ({akurasi_intent:.1f}%)  [Target >= 85.0%]")
    print(f"Akurasi Entity         : {benar_entity}/{total} ({akurasi_entity:.1f}%)")
    print(f"Deteksi Darurat (P0)   : {benar_darurat}/{total_darurat} ({akurasi_darurat:.1f}%)  [Target = 100.0%]")
    print("=" * 72)

    if gagal_detail:
        print("Daftar ketidaksesuaian:")
        for baris in gagal_detail:
            print(baris)

    if akurasi_intent < 85.0 or akurasi_darurat < 100.0:
        print("[GAGAL] Akurasi belum memenuhi ambang batas kualitas (NFR-02).")
        return 1

    print("[OK] Evaluasi NLU lulus semua ambang kualitas!")
    return 0


if __name__ == "__main__":
    sys.exit(jalankan_evaluasi())

