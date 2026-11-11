"""Dialog Manager & State Machine percakapan SIGAP (IDLE, MENUNGGU_KLARIFIKASI, MODE_DARURAT)."""

from typing import Dict, Any, Tuple, Optional
from core.model import Sesi, HasilNLU, KandidatIntent

_FASE_KE_INTENT = {
    "sebelum": "info_sebelum",
    "saat": "info_saat",
    "sesudah": "info_sesudah",
}

_INTENT_KE_FASE = {
    "info_sebelum": "sebelum",
    "info_saat": "saat",
    "info_sesudah": "sesudah",
}


def urai_payload_tombol(payload: str) -> Optional[Tuple[str, Optional[str], Dict[str, str]]]:
    """Mengurai payload tombol HTML (`m:<intent>:<entity>` atau `k:<pilihan>`).

    Mengembalikan tuple: (jenis, intent_tag, entity_dict) atau None jika bukan format tombol.
    """
    if not isinstance(payload, str):
        return None
    teks = payload.strip()
    if not (teks.startswith("m:") or teks.startswith("k:")):
        return None

    bagian = teks.split(":")
    jenis = bagian[0]  # 'm' atau 'k'

    if jenis == "m":
        intent_tag = bagian[1] if len(bagian) > 1 and bagian[1] else "menu_bantuan"
        entity: Dict[str, str] = {}
        if len(bagian) > 2 and bagian[2]:
            val1 = bagian[2]
            if intent_tag == "definisi_istilah":
                entity["istilah"] = val1
            elif intent_tag == "kelompok_rentan":
                entity["kelompok"] = val1
            else:
                entity["bencana"] = val1
        if len(bagian) > 3 and bagian[3]:
            entity["situasi"] = bagian[3]
        return ("m", intent_tag, entity)

    # jenis == "k" (jawaban klarifikasi)
    # Format bisa: k:gempa, k:info_saat:banjir, k:situasi:kendaraan, k:istilah:magnitudo, k:kelompok:anak_bayi
    if len(bagian) >= 3 and bagian[1] and bagian[2]:
        kunci = bagian[1]
        nilai = bagian[2]
        if kunci in ("info_sebelum", "info_saat", "info_sesudah", "tanda_peringatan", "penyebab", "situasi_khusus"):
            ent = {"bencana": nilai}
            if len(bagian) > 3 and bagian[3]:
                ent["situasi"] = bagian[3]
            return ("k", kunci, ent)
        if kunci in ("bencana", "fase", "situasi", "kelompok", "istilah"):
            return ("k", None, {kunci: nilai})
        if kunci == "intent":
            return ("k", nilai, {})

    pilihan = bagian[1] if len(bagian) > 1 else ""
    if pilihan in ("gempa", "banjir", "longsor", "tsunami", "gunung_api", "angin_kencang"):
        return ("k", None, {"bencana": pilihan})
    if pilihan in ("sebelum", "saat", "sesudah"):
        return ("k", _FASE_KE_INTENT[pilihan], {"fase": pilihan})
    return ("k", pilihan or None, {})


def putuskan_dialog(
    nlu: HasilNLU,
    sesi: Sesi,
    intents_map: Dict[str, Dict[str, Any]],
    waktu_sekarang: float,
) -> Tuple[str, HasilNLU, Sesi]:
    """Menentukan aksi dialog berikutnya dan memperbarui state Sesi.

    Aksi yang mungkin:
    - darurat
    - sapaan
    - tolak
    - klarifikasi
    - fallback
    - jawab
    """
    sesi_baru = Sesi.dari_dict(sesi.ke_dict())
    sesi_baru.aktivitas_terakhir = waktu_sekarang

    entity = dict(nlu.entity)
    terpilih = nlu.terpilih

    # 1. Jalur Darurat Aktif (P0 — Prioritas Tertinggi)
    if nlu.darurat or (terpilih and terpilih.tag == "darurat_aktif"):
        sesi_baru.status = "MODE_DARURAT"
        sesi_baru.klarifikasi_untuk = None
        sesi_baru.fallback_berturut = 0
        if "bencana" in entity:
            sesi_baru.bencana_terakhir = entity["bencana"]
        kandidat_darurat = KandidatIntent(tag="darurat_aktif", skor_mentah=6.0, confidence=1.0)
        nlu_darurat = HasilNLU(
            teks_bersih=nlu.teks_bersih,
            darurat=True,
            entity=entity,
            kandidat=nlu.kandidat or [kandidat_darurat],
            terpilih=kandidat_darurat,
            ambigu=False,
        )
        return "darurat", nlu_darurat, sesi_baru

    # Jika sebelumnya di MODE_DARURAT dan pesan baru non-darurat, kembali ke IDLE
    if sesi_baru.status == "MODE_DARURAT":
        sesi_baru.status = "IDLE"

    # 2. Jika sedang MENUNGGU_KLARIFIKASI, coba tafsirkan pesan sebagai jawaban klarifikasi
    if sesi_baru.status == "MENUNGGU_KLARIFIKASI":
        target_klarifikasi = sesi_baru.klarifikasi_untuk
        teks_trim = nlu.teks_bersih.strip()

        if target_klarifikasi == "bencana":
            peta_angka_bencana = {"1": "gempa", "2": "banjir", "3": "longsor"}
            if teks_trim in peta_angka_bencana:
                entity["bencana"] = peta_angka_bencana[teks_trim]
            if "bencana" in entity:
                intent_lanjut = sesi_baru.intent_terakhir or "info_saat"
                if terpilih and terpilih.tag in ("info_sebelum", "info_saat", "info_sesudah", "tanda_peringatan", "situasi_khusus"):
                    intent_lanjut = terpilih.tag
                terpilih = KandidatIntent(tag=intent_lanjut, skor_mentah=6.0, confidence=1.0)
                sesi_baru.status = "IDLE"
                sesi_baru.klarifikasi_untuk = None

        elif target_klarifikasi == "fase":
            bencana_aktif = entity.get("bencana") or sesi_baru.bencana_terakhir
            peta_angka_fase = {
                "1": "info_sebelum",
                "2": "info_saat",
                "3": "info_sesudah",
                "4": "tanda_peringatan",
                "5": "penyebab",
            }
            intent_fase = peta_angka_fase.get(teks_trim)
            if not intent_fase:
                if "fase" in entity and entity["fase"] in _FASE_KE_INTENT:
                    intent_fase = _FASE_KE_INTENT[entity["fase"]]
                elif terpilih and terpilih.tag in ("info_sebelum", "info_saat", "info_sesudah", "tanda_peringatan", "penyebab", "situasi_khusus"):
                    intent_fase = terpilih.tag
            if intent_fase and bencana_aktif:
                entity["bencana"] = bencana_aktif
                terpilih = KandidatIntent(tag=intent_fase, skor_mentah=6.0, confidence=1.0)
                sesi_baru.status = "IDLE"
                sesi_baru.klarifikasi_untuk = None

        elif target_klarifikasi == "situasi":
            bencana_aktif = entity.get("bencana") or sesi_baru.bencana_terakhir or "gempa"
            if bencana_aktif == "gempa":
                peta_sit = {"1": "kendaraan", "2": "gedung_tinggi", "3": "sekolah_kampus", "4": "pesisir", "5": "luar_ruangan", "6": "rumah"}
            elif bencana_aktif == "banjir":
                peta_sit = {"1": "kendaraan", "2": "rumah", "3": "lereng_gunung"}
            else:
                peta_sit = {"1": "lereng_gunung", "2": "rumah", "3": "kendaraan"}
            if teks_trim in peta_sit:
                entity["situasi"] = peta_sit[teks_trim]
            if "situasi" in entity and bencana_aktif:
                entity["bencana"] = bencana_aktif
                terpilih = KandidatIntent(tag="situasi_khusus", skor_mentah=6.0, confidence=1.0)
                sesi_baru.status = "IDLE"
                sesi_baru.klarifikasi_untuk = None

        elif target_klarifikasi == "kelompok":
            peta_kel = {"1": "anak_bayi", "2": "lansia", "3": "difabel", "4": "ibu_hamil", "5": "hewan_peliharaan"}
            if teks_trim in peta_kel:
                entity["kelompok"] = peta_kel[teks_trim]
            if "kelompok" in entity:
                terpilih = KandidatIntent(tag="kelompok_rentan", skor_mentah=6.0, confidence=1.0)
                sesi_baru.status = "IDLE"
                sesi_baru.klarifikasi_untuk = None

        elif target_klarifikasi == "istilah":
            peta_ist = {"1": "magnitudo", "2": "megathrust", "3": "episenter", "4": "status_gunung_api", "5": "mitigasi"}
            if teks_trim in peta_ist:
                entity["istilah"] = peta_ist[teks_trim]
            elif "istilah" not in entity and "bencana" in entity:
                entity["istilah"] = entity["bencana"]
            if "istilah" in entity:
                terpilih = KandidatIntent(tag="definisi_istilah", skor_mentah=6.0, confidence=1.0)
                sesi_baru.status = "IDLE"
                sesi_baru.klarifikasi_untuk = None

        elif target_klarifikasi == "intent" and terpilih is not None and not nlu.ambigu:
            sesi_baru.status = "IDLE"
            sesi_baru.klarifikasi_untuk = None

        # Jika pengguna ternyata menanyakan topik baru yang sudah lengkap, keluar dari mode klarifikasi
        if sesi_baru.status == "MENUNGGU_KLARIFIKASI" and terpilih is not None:
            sesi_baru.status = "IDLE"
            sesi_baru.klarifikasi_untuk = None

    # 3. Jika tidak ada intent yang lolos ambang confidence
    if terpilih is None:
        # Kasus Uji Kritis #5 & PDF K.INT-91.b:
        # Jika pengguna mengetik nama bencana sendirian (mis. "gempa" atau "banjir"), minta klarifikasi fase
        if "bencana" in entity:
            sesi_baru.bencana_terakhir = entity["bencana"]
            sesi_baru.status = "MENUNGGU_KLARIFIKASI"
            sesi_baru.klarifikasi_untuk = "fase"
            sesi_baru.fallback_berturut = 0
            nlu_baru = HasilNLU(
                teks_bersih=nlu.teks_bersih,
                darurat=False,
                entity=entity,
                kandidat=nlu.kandidat,
                terpilih=None,
                ambigu=False,
            )
            return "klarifikasi", nlu_baru, sesi_baru

        # Selain itu: Fallback bertahap
        sesi_baru.status = "IDLE"
        sesi_baru.klarifikasi_untuk = None
        sesi_baru.fallback_berturut += 1
        return "fallback", nlu, sesi_baru

    # 4. Jika intent ambigu (selisih dua kandidat teratas < 0.15)
    if nlu.ambigu:
        sesi_baru.status = "MENUNGGU_KLARIFIKASI"
        sesi_baru.klarifikasi_untuk = "intent"
        if "bencana" in entity:
            sesi_baru.bencana_terakhir = entity["bencana"]
        return "klarifikasi", nlu, sesi_baru

    # 5. Jika intent adalah permintaan prediksi bencana -> Tolak secara sopan (FR-10)
    if terpilih.tag == "prediksi":
        sesi_baru.status = "IDLE"
        sesi_baru.klarifikasi_untuk = None
        sesi_baru.fallback_berturut = 0
        sesi_baru.intent_terakhir = "prediksi"
        if "bencana" in entity:
            sesi_baru.bencana_terakhir = entity["bencana"]
        nlu_baru = HasilNLU(nlu.teks_bersih, False, entity, nlu.kandidat, terpilih, False)
        return "tolak", nlu_baru, sesi_baru

    # 6. Jika intent adalah sapaan
    if terpilih.tag == "sapaan":
        sesi_baru.status = "IDLE"
        sesi_baru.klarifikasi_untuk = None
        sesi_baru.fallback_berturut = 0
        sesi_baru.intent_terakhir = "sapaan"
        nlu_baru = HasilNLU(nlu.teks_bersih, False, entity, nlu.kandidat, terpilih, False)
        return "sapaan", nlu_baru, sesi_baru

    # 7. Periksa kelengkapan entity wajib untuk intent terpilih
    info_intent = intents_map.get(terpilih.tag, {})
    entity_wajib = info_intent.get("entity_wajib", [])
    if terpilih.tag == "definisi_istilah" and "istilah" not in entity and "bencana" in entity:
        entity["istilah"] = entity["bencana"]
    for syarat in entity_wajib:
        if syarat not in entity or not entity[syarat]:
            # Khusus definisi_istilah tanpa istilah spesifik: tampilkan glosarium interaktif atau klarifikasi
            sesi_baru.status = "MENUNGGU_KLARIFIKASI"
            sesi_baru.klarifikasi_untuk = syarat
            sesi_baru.intent_terakhir = terpilih.tag
            if "bencana" in entity:
                sesi_baru.bencana_terakhir = entity["bencana"]
            sesi_baru.fallback_berturut = 0
            nlu_baru = HasilNLU(nlu.teks_bersih, False, entity, nlu.kandidat, terpilih, False)
            return "klarifikasi", nlu_baru, sesi_baru

    # 8. Semua syarat terpenuhi -> Jawab
    sesi_baru.status = "IDLE"
    sesi_baru.klarifikasi_untuk = None
    sesi_baru.fallback_berturut = 0
    sesi_baru.intent_terakhir = terpilih.tag
    if "bencana" in entity:
        sesi_baru.bencana_terakhir = entity["bencana"]
    if terpilih.tag in _INTENT_KE_FASE:
        sesi_baru.fase_terakhir = _INTENT_KE_FASE[terpilih.tag]
    elif "fase" in entity:
        sesi_baru.fase_terakhir = entity["fase"]

    nlu_baru = HasilNLU(nlu.teks_bersih, False, entity, nlu.kandidat, terpilih, False)
    return "jawab", nlu_baru, sesi_baru

