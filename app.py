"""Titik masuk utama aplikasi web Flask SIGAP (Sistem Informasi Gawat Darurat dan Antisipasi Penanggulangan)."""

import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

from flask import Flask, request, jsonify, session, render_template, abort

import config
import kb_loader
from core.engine import Core
from core.model import PesanMasuk, Sesi, Keputusan
from core.responder import _buat_tombol_dari_spek, _format_teks_dengan_sumber
from web.formatter import ke_html
from db import repository
from db.koneksi import cek_status_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sigap.app")

BASE_DIR = Path(__file__).resolve().parent

# Pencatat batas laju (rate limiter) sederhana di memori per sesi: sid -> list[timestamp]
_CATATAN_LAJU: Dict[str, List[float]] = {}


def keputusan_ke_debug(keputusan: Keputusan) -> Dict[str, Any]:
    """Mengubah objek Keputusan menjadi struktur dictionary debug sesuai kontrak API Bagian 9.2."""
    nlu = keputusan.nlu
    return {
        "intent": nlu.terpilih.tag if nlu.terpilih else None,
        "confidence": nlu.terpilih.confidence if nlu.terpilih else 0.0,
        "entity": nlu.entity,
        "aksi": keputusan.aksi,
        "kandidat": [[k.tag, k.confidence] for k in nlu.kandidat[:5]],
    }


def _salam_awal(kb_aktif: Any) -> Dict[str, Any]:
    """Menyusun data salam pembuka dan tombol menu awal untuk /api/mulai dan /api/reset."""
    resp = kb_aktif.ambil_respons("sapaan", {})
    if not resp:
        teks = (
            "Halo! Aku **SIGAP** 👋, asisten kesiapsiagaan bencana.\n"
            "Pilih topik di bawah atau ketik pertanyaanmu. Dalam keadaan darurat, hubungi **112**."
        )
        tombol_spek = ["info_saat:gempa", "info_saat:banjir", "info_saat:longsor", "tas_siaga", "kontak_darurat"]
        id_resp = "RSP-U1"
    else:
        teks = _format_teks_dengan_sumber(resp, darurat=False)
        tombol_spek = resp.get("tombol", ["info_saat:gempa", "info_saat:banjir", "info_saat:longsor", "tas_siaga"])
        id_resp = resp.get("id", "RSP-U1")

    tombol_list = [_buat_tombol_dari_spek(s).__dict__ for s in tombol_spek]
    return {
        "balasan": {
            "html": ke_html(teks),
            "tombol": tombol_list,
            "darurat": False,
        },
        "id_respons": id_resp,
        "mode_bawaan": bool(getattr(kb_aktif, "mode_bawaan", False)),
    }


def _periksa_batas_laju(sid: str, sekarang: float) -> bool:
    """Mengembalikan True jika sesi masih di bawah batas pesan_per_menit, False jika melampaui."""
    batas = int(config.BATAS.get("pesan_per_menit", 20))
    jendela = [t for t in _CATATAN_LAJU.get(sid, []) if sekarang - t < 60.0]
    if len(jendela) >= batas:
        _CATATAN_LAJU[sid] = jendela
        return False
    jendela.append(sekarang)
    _CATATAN_LAJU[sid] = jendela
    return True


def buat_app(kb_path: str | Path | None = None, aktifkan_batas_laju: bool = True) -> Flask:
    """Factory pembuatan aplikasi Flask SIGAP (memudahkan pengujian dengan KB kustom)."""
    aplikasi = Flask(
        __name__,
        template_folder=str(BASE_DIR / "web" / "templates"),
        static_folder=str(BASE_DIR / "web" / "static"),
    )
    aplikasi.secret_key = config.SECRET_KEY
    aplikasi.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    jalur_kb = kb_path if kb_path is not None else config.KB_PATH
    kb_inst, is_mode_bawaan = kb_loader.muat_atau_bawaan(jalur_kb)
    core_inst = Core(kb_inst, config.NLU, config.SESI)

    aplikasi.config["SIGAP_KB"] = kb_inst
    aplikasi.config["SIGAP_CORE"] = core_inst
    aplikasi.config["SIGAP_MODE_BAWAAN"] = is_mode_bawaan
    aplikasi.config["SIGAP_RATE_LIMIT"] = aktifkan_batas_laju

    @aplikasi.get("/")
    def index():
        session.setdefault("sid", uuid.uuid4().hex)
        return render_template(
            "index.html",
            mode_bawaan=aplikasi.config["SIGAP_MODE_BAWAAN"],
        )

    @aplikasi.get("/api/mulai")
    def mulai():
        session.setdefault("sid", uuid.uuid4().hex)
        session.setdefault("sesi", Sesi().ke_dict())
        return jsonify(_salam_awal(aplikasi.config["SIGAP_KB"]))

    @aplikasi.post("/api/chat")
    def chat():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Pesan tidak valid"), 400

        teks = data.get("pesan")
        tombol_payload = data.get("tombol")

        if not isinstance(teks, str) or not teks.strip():
            return jsonify(error="Pesan tidak valid"), 400

        maks_karakter = int(config.BATAS.get("panjang_pesan_maks", 1000))
        if len(teks) > maks_karakter:
            return jsonify(error="Pesan terlalu panjang"), 413

        if tombol_payload is not None and (not isinstance(tombol_payload, str) or len(tombol_payload) > 200):
            return jsonify(error="Payload tombol tidak valid"), 400

        sid = session.setdefault("sid", uuid.uuid4().hex)
        mulai_waktu = time.time()

        if aplikasi.config.get("SIGAP_RATE_LIMIT", True):
            if not _periksa_batas_laju(sid, mulai_waktu):
                return jsonify(error="Terlalu cepat, coba sebentar lagi"), 429

        sesi_lama = Sesi.dari_dict(session.get("sesi"))
        core_engine: Core = aplikasi.config["SIGAP_CORE"]
        kb_aktif = aplikasi.config["SIGAP_KB"]

        try:
            pesan_masuk = PesanMasuk(
                teks=tombol_payload.strip() if (isinstance(tombol_payload, str) and tombol_payload.strip()) else teks,
                adalah_tombol=bool(tombol_payload),
                waktu_epoch=mulai_waktu,
            )
            balasan, sesi_baru, keputusan = core_engine.proses(pesan_masuk, sesi_lama)
            session["sesi"] = sesi_baru.ke_dict()

            latensi_ms = int((time.time() - mulai_waktu) * 1000)
            intent_log = keputusan.nlu.terpilih.tag if keputusan.nlu.terpilih else "none"
            conf_log = keputusan.nlu.terpilih.confidence if keputusan.nlu.terpilih else 0.0
            logger.info(
                "intent=%s conf=%.2f aksi=%s resp=%s %dms",
                intent_log,
                conf_log,
                keputusan.aksi,
                balasan.id_respons or "-",
                latensi_ms,
            )

            repository.catat_keputusan_aman(
                sesi_id=sid,
                keputusan=keputusan,
                balasan=balasan,
                versi_kb=kb_aktif.versi,
                latensi_ms=latensi_ms,
                teks_asli=teks,
            )

            payload_respons: Dict[str, Any] = {
                "balasan": {
                    "html": ke_html(balasan.teks),
                    "tombol": [t.__dict__ for t in balasan.tombol],
                    "darurat": balasan.darurat,
                },
                "id_respons": balasan.id_respons,
            }

            return jsonify(payload_respons), 200

        except Exception:
            logger.exception("Kesalahan internal pada pipeline /api/chat")
            # Balasan aman (kontak darurat + menu), bukan stack trace (Bagian 9.2 & 10)
            teks_aman = (
                "Maaf, terjadi gangguan teknis sementara pada sistem.\n"
                "1. Dalam keadaan darurat, segera hubungi nomor **112** atau Basarnas **115**.\n"
                "2. Silakan pilih salah satu topik panduan dasar di bawah ini:"
            )
            return (
                jsonify(
                    balasan={
                        "html": ke_html(teks_aman),
                        "tombol": [
                            {"label": "Saat Gempa", "payload": "m:info_saat:gempa"},
                            {"label": "Saat Banjir", "payload": "m:info_saat:banjir"},
                            {"label": "Saat Longsor", "payload": "m:info_saat:longsor"},
                            {"label": "Kontak Darurat", "payload": "m:kontak_darurat:"},
                        ],
                        "darurat": True,
                    },
                    id_respons="ERR-SAFE-500",
                ),
                500,
            )

    @aplikasi.post("/api/feedback")
    def feedback():
        data = request.get_json(silent=True) or {}
        id_respons = data.get("id_respons")
        nilai = data.get("nilai")

        if not isinstance(id_respons, str) or not id_respons.strip() or nilai not in (1, -1, "1", "-1"):
            return jsonify(error="Data feedback tidak valid"), 400

        sid = session.setdefault("sid", uuid.uuid4().hex)
        kb_aktif = aplikasi.config["SIGAP_KB"]
        tersimpan = repository.catat_feedback_aman(sid, id_respons.strip(), int(nilai), kb_aktif.versi)
        return jsonify(ok=True, tersimpan_db=tersimpan), 200

    @aplikasi.post("/api/reset")
    def reset():
        session["sesi"] = Sesi().ke_dict()
        session["sid"] = uuid.uuid4().hex
        return jsonify(_salam_awal(aplikasi.config["SIGAP_KB"])), 200

    @aplikasi.get("/health")
    def health():
        kb_aktif = aplikasi.config["SIGAP_KB"]
        mode_bawaan_aktif = aplikasi.config["SIGAP_MODE_BAWAAN"]
        status_db = cek_status_db()
        return (
            jsonify(
                status="ok",
                kb="mode_bawaan" if mode_bawaan_aktif else "tersedia",
                versi_kb=kb_aktif.versi,
                mode_bawaan=mode_bawaan_aktif,
                db=status_db,
            ),
            200,
        )

    return aplikasi


app = buat_app()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)

