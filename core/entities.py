"""Ekstraksi entity (bencana, fase, situasi, kelompok rentan, istilah) dari teks bersih."""

import re
from typing import Dict, Any
from rapidfuzz import fuzz


def ada_dengan_batas_kata(frasa: str, teks: str) -> bool:
    """Memeriksa apakah frasa muncul utuh dengan batas kata di dalam teks."""
    if not frasa or not teks:
        return False
    pola = r"(?<!\w)" + re.escape(frasa) + r"(?!\w)"
    return bool(re.search(pola, teks))


def _fuzzy_kata(frasa: str, daftar_kata_teks: list[str], ambang: float, min_panjang: int) -> float:
    """Mencocokkan frasa terhadap jendela kata (n-gram) di teks menggunakan rapidfuzz."""
    kata_frasa = frasa.split()
    n = len(kata_frasa)
    if n == 0 or len(daftar_kata_teks) < n:
        return 0.0

    # Hanya jalankan fuzzy bila kata cukup panjang (>= min_panjang)
    if any(len(k) < min_panjang for k in kata_frasa):
        return 0.0

    skor_terbaik = 0.0
    for i in range(len(daftar_kata_teks) - n + 1):
        jendela = daftar_kata_teks[i : i + n]
        if any(len(k) < min_panjang - 1 for k in jendela):
            continue
        kandidat_str = " ".join(jendela)
        sim = fuzz.ratio(frasa, kandidat_str) / 100.0
        if sim >= ambang and sim > skor_terbaik:
            skor_terbaik = sim
    return skor_terbaik


def ekstrak_entity(teks_bersih: str, kb_entities: Dict[str, Any], cfg: Dict[str, Any] | None = None) -> Dict[str, str]:
    """Mengekstrak entity bencana, fase, situasi, kelompok, dan istilah dari teks bersih."""
    if not teks_bersih or not kb_entities:
        return {}

    cfg = cfg or {}
    ambang_fuzzy = float(cfg.get("ambang_fuzzy", 0.85))
    min_panjang = int(cfg.get("fuzzy_min_panjang_kata", 4))
    daftar_kata = teks_bersih.split()

    hasil: Dict[str, str] = {}

    # 1. Ekstraksi Bencana (pilih kecocokan persis terpanjang atau prioritas P1, lalu fuzzy)
    bencana_map = kb_entities.get("bencana", {})
    kandidat_bencana = []
    for kode_bencana, info in bencana_map.items():
        prioritas = info.get("prioritas", 2)
        sinonim_list = info.get("sinonim", [])
        for sin in sinonim_list:
            if ada_dengan_batas_kata(sin, teks_bersih):
                kandidat_bencana.append((1.0, len(sin), -prioritas, kode_bencana))
            else:
                sim = _fuzzy_kata(sin, daftar_kata, ambang_fuzzy, min_panjang)
                if sim >= ambang_fuzzy:
                    kandidat_bencana.append((sim, len(sin), -prioritas, kode_bencana))
    if kandidat_bencana:
        kandidat_bencana.sort(reverse=True)
        hasil["bencana"] = kandidat_bencana[0][3]

    # 2. Ekstraksi Fase (sebelum, saat, sesudah)
    fase_map = kb_entities.get("fase", {})
    kandidat_fase = []
    for kode_fase, info in fase_map.items():
        sinonim_list = info.get("sinonim", []) if isinstance(info, dict) else info
        for sin in sinonim_list:
            if ada_dengan_batas_kata(sin, teks_bersih):
                kandidat_fase.append((1.0, len(sin), kode_fase))
            else:
                sim = _fuzzy_kata(sin, daftar_kata, ambang_fuzzy, min_panjang)
                if sim >= ambang_fuzzy:
                    kandidat_fase.append((sim, len(sin), kode_fase))
    if kandidat_fase:
        kandidat_fase.sort(reverse=True)
        hasil["fase"] = kandidat_fase[0][2]

    # 3. Ekstraksi Situasi Khusus (kendaraan, gedung_tinggi, sekolah_kampus, pesisir, luar_ruangan, rumah, lereng_gunung)
    situasi_map = kb_entities.get("situasi", {})
    kandidat_situasi = []
    for kode_sit, info in situasi_map.items():
        sinonim_list = info.get("sinonim", []) if isinstance(info, dict) else info
        for sin in sinonim_list:
            if ada_dengan_batas_kata(sin, teks_bersih):
                kandidat_situasi.append((1.0, len(sin), kode_sit))
            else:
                sim = _fuzzy_kata(sin, daftar_kata, ambang_fuzzy, min_panjang)
                if sim >= ambang_fuzzy:
                    kandidat_situasi.append((sim, len(sin), kode_sit))
    if kandidat_situasi:
        kandidat_situasi.sort(reverse=True)
        hasil["situasi"] = kandidat_situasi[0][2]

    # 4. Ekstraksi Kelompok Rentan
    kelompok_map = kb_entities.get("kelompok", {})
    kandidat_kelompok = []
    for kode_kel, info in kelompok_map.items():
        sinonim_list = info.get("sinonim", []) if isinstance(info, dict) else info
        for sin in sinonim_list:
            if ada_dengan_batas_kata(sin, teks_bersih):
                kandidat_kelompok.append((1.0, len(sin), kode_kel))
            else:
                sim = _fuzzy_kata(sin, daftar_kata, ambang_fuzzy, min_panjang)
                if sim >= ambang_fuzzy:
                    kandidat_kelompok.append((sim, len(sin), kode_kel))
    if kandidat_kelompok:
        kandidat_kelompok.sort(reverse=True)
        hasil["kelompok"] = kandidat_kelompok[0][2]

    # 5. Ekstraksi Istilah Kebencanaan (Glosarium)
    istilah_map = kb_entities.get("istilah", {})
    kandidat_istilah = []
    for kode_ist, sinonim_list in istilah_map.items():
        if isinstance(sinonim_list, dict):
            sinonim_list = sinonim_list.get("sinonim", [])
        for idx_s, sin in enumerate(sinonim_list):
            if ada_dengan_batas_kata(sin, teks_bersih):
                # Utamakan posisi kemunculan lebih awal di teks jika panjang frasa setara
                pos = teks_bersih.find(sin)
                kandidat_istilah.append((1.0, len(sin.split()), -pos, kode_ist))
            else:
                sim = _fuzzy_kata(sin, daftar_kata, ambang_fuzzy, min_panjang)
                if sim >= ambang_fuzzy:
                    kandidat_istilah.append((sim, len(sin.split()), 0, kode_ist))
    if kandidat_istilah:
        kandidat_istilah.sort(reverse=True)
        hasil["istilah"] = kandidat_istilah[0][3]

    return hasil

