"""Skoring dan klasifikasi intent dengan perhitungan confidence (0..1) dan fuzzy matching."""

from typing import List, Dict, Any, Tuple, Optional, Set
from rapidfuzz import fuzz
from core.model import KandidatIntent
from core.entities import ada_dengan_batas_kata


def fuzzy_partial(
    frasa: str,
    teks: str,
    min_panjang: int = 4,
    jendela_terpakai: Optional[Set[str]] = None,
) -> float:
    """Menghitung kemiripan terbaik (0..1) antara frasa dan n-gram kata di dalam teks.

    Catatan sesuai Bagian 6.4:
    - Pencocokan menghormati batas kata ("saat" tidak cocok dengan "sesaat").
    - Frasa multi-kata dihitung satu kecocokan.
    - Fuzzy hanya dijalankan untuk kata >= 4 huruf dan tidak menghitung ganda jendela
      yang sudah cocok persis pada intent yang sama.
    """
    if not frasa or not teks:
        return 0.0

    kata_frasa = frasa.split()
    if any(len(k) < min_panjang for k in kata_frasa):
        return 0.0

    kata_teks = teks.split()
    n = len(kata_frasa)
    if len(kata_teks) < n:
        return 0.0

    terpakai = jendela_terpakai or set()
    terbaik = 0.0
    for i in range(len(kata_teks) - n + 1):
        jendela = kata_teks[i : i + n]
        if any(len(k) < min_panjang - 1 for k in jendela):
            continue
        kandidat = " ".join(jendela)
        if kandidat in terpakai:
            continue
        sim = fuzz.ratio(frasa, kandidat) / 100.0
        if sim > terbaik:
            terbaik = sim
    return terbaik


def cocok(
    frasa: str,
    teks: str,
    ambang: float = 0.85,
    min_panjang: int = 4,
    jendela_terpakai: Optional[Set[str]] = None,
) -> float:
    """Mengembalikan 1.0 jika cocok persis dengan batas kata, atau similarity jika >= ambang."""
    if ada_dengan_batas_kata(frasa, teks):
        return 1.0
    sim = fuzzy_partial(frasa, teks, min_panjang=min_panjang, jendela_terpakai=jendela_terpakai)
    return sim if sim >= ambang else 0.0


def skor_intent(
    teks_bersih: str,
    intents_kb: List[Dict[str, Any]],
    cfg: Dict[str, Any] | None = None,
    intent_terakhir: Optional[str] = None,
) -> Tuple[List[KandidatIntent], Optional[KandidatIntent], bool]:
    """Menghitung skor seluruh intent dan menentukan intent terpilih serta status ambigu.

    Rumus Bagian 6.3 & 6.4:
    - Bobot kata kunci kuat = 3, pendukung = 1
    - confidence = min(1.0, skor_mentah / 6)
    - ambang_confidence = 0.5
    - ambang_selisih_ambigu = 0.15
    """
    cfg = cfg or {}
    bobot_kuat = float(cfg.get("bobot_kuat", 3.0))
    bobot_pendukung = float(cfg.get("bobot_pendukung", 1.0))
    skor_penuh = float(cfg.get("skor_penuh", 6.0))
    ambang_conf = float(cfg.get("ambang_confidence", 0.5))
    ambang_ambigu = float(cfg.get("ambang_selisih_ambigu", 0.15))
    ambang_fuzzy = float(cfg.get("ambang_fuzzy", 0.85))
    min_panjang = int(cfg.get("fuzzy_min_panjang_kata", 4))

    if not teks_bersih:
        return [], None, False

    peta_prioritas: Dict[str, int] = {}
    kandidat_list: List[KandidatIntent] = []

    for it in intents_kb:
        tag = it["tag"]
        peta_prioritas[tag] = int(it.get("prioritas", 1))
        kuat_list = it.get("kuat", [])
        pendukung_list = it.get("pendukung", [])

        # Catat frasa yang sudah cocok persis pada intent ini agar tidak dihitung ganda oleh fuzzy sinonim
        persis_terpakai: Set[str] = set()
        for frasa in kuat_list + pendukung_list:
            if ada_dengan_batas_kata(frasa, teks_bersih):
                persis_terpakai.add(frasa)

        mentah = 0.0
        for frasa in kuat_list:
            mentah += bobot_kuat * cocok(frasa, teks_bersih, ambang_fuzzy, min_panjang, persis_terpakai)
        for frasa in pendukung_list:
            mentah += bobot_pendukung * cocok(frasa, teks_bersih, ambang_fuzzy, min_panjang, persis_terpakai)

        conf = round(min(1.0, mentah / skor_penuh), 2)
        if mentah > 0:
            kandidat_list.append(KandidatIntent(tag=tag, skor_mentah=round(mentah, 3), confidence=conf))

    # Urutkan berdasarkan: confidence tertinggi, skor_mentah tertinggi, prioritas (0 < 1 < 2),
    # lalu kesamaan dengan intent_terakhir pada konteks sesi
    kandidat_list.sort(
        key=lambda k: (
            -k.confidence,
            -k.skor_mentah,
            peta_prioritas.get(k.tag, 2),
            0 if (intent_terakhir and k.tag == intent_terakhir) else 1,
            k.tag,
        )
    )

    if not kandidat_list or kandidat_list[0].confidence < ambang_conf:
        return kandidat_list, None, False

    terpilih = kandidat_list[0]
    ambigu = False

    # Cek apakah kandidat kedua juga lolos ambang dan selisihnya < ambang_selisih_ambigu
    # Catatan: intent 'lanjutan' adalah penanda wacana dan tidak memicu ambiguitas terhadap intent substantif
    kandidat_substantif = [k for k in kandidat_list if k.tag != "lanjutan"]
    if len(kandidat_substantif) >= 2:
        k1, k2 = kandidat_substantif[0], kandidat_substantif[1]
        if k1.confidence >= ambang_conf and k2.confidence >= ambang_conf:
            selisih = round(k1.confidence - k2.confidence, 4)
            # Jika prioritas sama dan selisih < 0.15, tandai ambigu
            if selisih < ambang_ambigu and peta_prioritas.get(k1.tag, 1) == peta_prioritas.get(k2.tag, 1):
                ambigu = True

    return kandidat_list, terpilih, ambigu
