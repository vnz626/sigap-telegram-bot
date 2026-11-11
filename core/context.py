"""Resolusi konteks percakapan multi-giliran dan penanganan kedaluwarsa sesi (TTL)."""

from typing import Dict, Any, Tuple, Optional
from core.model import Sesi, KandidatIntent

_FASE_KE_INTENT = {
    "sebelum": "info_sebelum",
    "saat": "info_saat",
    "sesudah": "info_sesudah",
}


def periksa_ttl_sesi(sesi: Sesi, waktu_sekarang: float, cfg_sesi: Dict[str, Any] | None = None) -> Sesi:
    """Memeriksa apakah konteks sesi atau status klarifikasi sudah kedaluwarsa."""
    cfg_sesi = cfg_sesi or {}
    ttl_detik = float(cfg_sesi.get("ttl_detik", 600))
    klarifikasi_timeout = float(cfg_sesi.get("klarifikasi_timeout_detik", 300))

    sesi_baru = Sesi.dari_dict(sesi.ke_dict())

    if sesi_baru.aktivitas_terakhir > 0 and waktu_sekarang > 0:
        selisih = waktu_sekarang - sesi_baru.aktivitas_terakhir
        if selisih > ttl_detik:
            # Konteks kedaluwarsa setelah 10 menit tanpa aktivitas
            sesi_baru.bencana_terakhir = None
            sesi_baru.fase_terakhir = None
            sesi_baru.intent_terakhir = None
            sesi_baru.status = "IDLE"
            sesi_baru.klarifikasi_untuk = None
            sesi_baru.fallback_berturut = 0
        elif sesi_baru.status == "MENUNGGU_KLARIFIKASI" and selisih > klarifikasi_timeout:
            # Klarifikasi kedaluwarsa setelah 5 menit
            sesi_baru.status = "IDLE"
            sesi_baru.klarifikasi_untuk = None
        elif sesi_baru.status == "MODE_DARURAT" and selisih > ttl_detik:
            sesi_baru.status = "IDLE"

    return sesi_baru


def resolusi_konteks(
    entity: Dict[str, str],
    terpilih: Optional[KandidatIntent],
    sesi: Sesi,
    intents_map: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, str], Optional[KandidatIntent]]:
    """Mengisi entity kosong dari sesi dan menerjemahkan pertanyaan lanjutan."""
    entity_baru = dict(entity)
    intent_hasil = terpilih

    # 1. Jika intent yang terpilih adalah 'lanjutan' (mis. "kalau banjir?", "kalau di mobil?")
    if intent_hasil and intent_hasil.tag == "lanjutan":
        if "fase" in entity_baru and entity_baru["fase"] in _FASE_KE_INTENT:
            tag_target = _FASE_KE_INTENT[entity_baru["fase"]]
            intent_hasil = KandidatIntent(tag=tag_target, skor_mentah=intent_hasil.skor_mentah, confidence=intent_hasil.confidence)
        elif "situasi" in entity_baru and (entity_baru.get("bencana") or sesi.bencana_terakhir):
            intent_hasil = KandidatIntent(tag="situasi_khusus", skor_mentah=intent_hasil.skor_mentah, confidence=intent_hasil.confidence)
        elif "kelompok" in entity_baru:
            intent_hasil = KandidatIntent(tag="kelompok_rentan", skor_mentah=intent_hasil.skor_mentah, confidence=intent_hasil.confidence)
        elif sesi.intent_terakhir and sesi.intent_terakhir != "lanjutan":
            intent_hasil = KandidatIntent(
                tag=sesi.intent_terakhir,
                skor_mentah=intent_hasil.skor_mentah,
                confidence=intent_hasil.confidence,
            )

    # 2. Jika belum ada intent terpilih namun pengguna berada dalam alur konteks aktif
    if intent_hasil is None and sesi.status != "MENUNGGU_KLARIFIKASI":
        if "situasi" in entity_baru and (entity_baru.get("bencana") or sesi.bencana_terakhir):
            intent_hasil = KandidatIntent(tag="situasi_khusus", skor_mentah=3.0, confidence=0.5)
        elif "fase" in entity_baru and sesi.bencana_terakhir and "bencana" not in entity_baru:
            tag_target = _FASE_KE_INTENT.get(entity_baru["fase"])
            if tag_target:
                intent_hasil = KandidatIntent(tag=tag_target, skor_mentah=3.0, confidence=0.5)

    # 3. Isi entity 'bencana' dari sesi.bencana_terakhir bila intent membutuhkannya atau relevan
    if "bencana" not in entity_baru and sesi.bencana_terakhir:
        if intent_hasil is not None:
            info_it = intents_map.get(intent_hasil.tag, {})
            wajib = info_it.get("entity_wajib", [])
            if "bencana" in wajib or intent_hasil.tag in ("jalur_evakuasi", "tas_siaga"):
                entity_baru["bencana"] = sesi.bencana_terakhir

    return entity_baru, intent_hasil

