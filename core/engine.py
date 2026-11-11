"""Engine utama SIGAP: menggabungkan seluruh pipeline NLU, konteks, dialog, dan responder."""

from typing import Tuple, Dict, Any
from core.model import PesanMasuk, Sesi, HasilNLU, Balasan, Keputusan, KandidatIntent
from core.normalizer import normalisasi
from core.emergency import deteksi_darurat
from core.entities import ekstrak_entity
from core.intents import skor_intent
from core.context import periksa_ttl_sesi, resolusi_konteks
from core.dialog import urai_payload_tombol, putuskan_dialog
from core.responder import bangun_balasan


class Core:
    """Mesin pemroses percakapan murni (tanpa I/O jaringan, database, atau jam sistem)."""

    def __init__(self, kb: Any, cfg: Dict[str, Any] | None = None, cfg_sesi: Dict[str, Any] | None = None):
        self.kb = kb
        self.cfg = cfg or {
            "bobot_kuat": 3,
            "bobot_pendukung": 1,
            "skor_penuh": 6,
            "ambang_confidence": 0.5,
            "ambang_selisih_ambigu": 0.15,
            "ambang_fuzzy": 0.85,
            "fuzzy_min_panjang_kata": 4,
        }
        self.cfg_sesi = cfg_sesi or {
            "ttl_detik": 600,
            "klarifikasi_timeout_detik": 300,
            "fallback_sebelum_menu": 2,
        }

    def _proses_tombol(
        self,
        info_tombol: Tuple[str, str | None, Dict[str, str]],
        teks_asli: str,
        sesi_aktif: Sesi,
        waktu_epoch: float,
    ) -> Tuple[Balasan, Sesi, Keputusan]:
        jenis, intent_tag, ent_tombol = info_tombol
        entityGabung = dict(ent_tombol)

        if jenis == "k":
            # Tombol jawaban klarifikasi: gabungkan dengan konteks sesi
            if "bencana" not in entityGabung and sesi_aktif.bencana_terakhir:
                entityGabung["bencana"] = sesi_aktif.bencana_terakhir
            if not intent_tag:
                intent_tag = sesi_aktif.intent_terakhir or "info_saat"
            sesi_aktif.status = "IDLE"
            sesi_aktif.klarifikasi_untuk = None
        else:
            # Tombol menu/navigasi (m:...)
            if not intent_tag:
                intent_tag = "menu_bantuan"
            sesi_aktif.status = "IDLE"
            sesi_aktif.klarifikasi_untuk = None

        kandidat_pilih = KandidatIntent(tag=intent_tag, skor_mentah=6.0, confidence=1.0)
        nlu_awal = HasilNLU(
            teks_bersih=teks_asli.strip().lower(),
            darurat=(intent_tag == "darurat_aktif"),
            entity=entityGabung,
            kandidat=[kandidat_pilih],
            terpilih=kandidat_pilih,
            ambigu=False,
        )
        aksi, nlu_final, sesi_baru = putuskan_dialog(nlu_awal, sesi_aktif, self.kb.intents_map, waktu_epoch)
        keputusan = Keputusan(nlu=nlu_final, aksi=aksi)
        balasan = bangun_balasan(keputusan, sesi_baru, self.kb, self.cfg_sesi)
        return balasan, sesi_baru, keputusan

    def proses(self, pesan: PesanMasuk, sesi: Sesi | None = None) -> Tuple[Balasan, Sesi, Keputusan]:
        """Fungsi murni: memproses satu PesanMasuk dan mengembalikan (Balasan, Sesi baru, Keputusan)."""
        sesi_awal = sesi if isinstance(sesi, Sesi) else Sesi.dari_dict(sesi if isinstance(sesi, dict) else None)
        waktu_epoch = float(pesan.waktu_epoch or 0.0)

        # 1. Periksa kedaluwarsa sesi (TTL 10 menit / klarifikasi 5 menit)
        sesi_aktif = periksa_ttl_sesi(sesi_awal, waktu_epoch, self.cfg_sesi)

        teks_mentah = pesan.teks if isinstance(pesan.teks, str) else ""

        # 2. Jika input berasal dari tombol (payload m:... atau k:...)
        info_tombol = urai_payload_tombol(teks_mentah)
        if info_tombol is not None:
            return self._proses_tombol(info_tombol, teks_mentah, sesi_aktif, waktu_epoch)

        # 3. Normalisasi teks
        teks_bersih = normalisasi(teks_mentah, self.kb.slang)

        # Jika pesan kosong, hanya spasi, atau hanya emoji/simbol (Kasus Uji Kritis #8)
        if not teks_bersih:
            sesi_baru = Sesi.dari_dict(sesi_aktif.ke_dict())
            sesi_baru.aktivitas_terakhir = waktu_epoch
            nlu_kosong = HasilNLU(
                teks_bersih="",
                darurat=False,
                entity={},
                kandidat=[],
                terpilih=None,
                ambigu=False,
            )
            keputusan = Keputusan(nlu=nlu_kosong, aksi="fallback")
            balasan = bangun_balasan(keputusan, sesi_baru, self.kb, self.cfg_sesi)
            return balasan, sesi_baru, keputusan

        # 4. Deteksi Darurat Aktif (P0 — sebelum skoring intent)
        is_darurat = deteksi_darurat(teks_bersih)

        # 5. Ekstraksi Entity
        entity = ekstrak_entity(teks_bersih, self.kb.entities, self.cfg)

        # 6. Jika darurat aktif, langsung lompat ke Dialog Manager & Response Builder
        if is_darurat:
            nlu_darurat = HasilNLU(
                teks_bersih=teks_bersih,
                darurat=True,
                entity=entity,
                kandidat=[KandidatIntent(tag="darurat_aktif", skor_mentah=6.0, confidence=1.0)],
                terpilih=KandidatIntent(tag="darurat_aktif", skor_mentah=6.0, confidence=1.0),
                ambigu=False,
            )
            aksi, nlu_final, sesi_baru = putuskan_dialog(nlu_darurat, sesi_aktif, self.kb.intents_map, waktu_epoch)
            keputusan = Keputusan(nlu=nlu_final, aksi=aksi)
            balasan = bangun_balasan(keputusan, sesi_baru, self.kb, self.cfg_sesi)
            return balasan, sesi_baru, keputusan

        # 7. Skoring Intent
        kandidat, terpilih, ambigu = skor_intent(
            teks_bersih,
            self.kb.intents,
            self.cfg,
            intent_terakhir=sesi_aktif.intent_terakhir,
        )

        # 8. Resolusi Konteks (isi entity kosong dari sesi bila relevan)
        entity_res, terpilih_res = resolusi_konteks(
            entity,
            terpilih,
            sesi_aktif,
            self.kb.intents_map,
        )

        # Jika sebelumnya ambigu hanya terhadap 'lanjutan', pastikan ambigu dihitung ulang
        nlu_hasil = HasilNLU(
            teks_bersih=teks_bersih,
            darurat=False,
            entity=entity_res,
            kandidat=kandidat,
            terpilih=terpilih_res,
            ambigu=ambigu,
        )

        # 9. Keputusan Dialog Manager & Pembentukan Respons
        aksi, nlu_final, sesi_baru = putuskan_dialog(nlu_hasil, sesi_aktif, self.kb.intents_map, waktu_epoch)
        keputusan = Keputusan(nlu=nlu_final, aksi=aksi)
        balasan = bangun_balasan(keputusan, sesi_baru, self.kb, self.cfg_sesi)
        return balasan, sesi_baru, keputusan

