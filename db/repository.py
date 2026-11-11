"""Repository penyimpanan log keputusan, ucapan tidak dikenali, dan feedback ke MySQL XAMPP.

Prinsip utama Bagian 8 & 10:
- Kegagalan database TIDAK BOLEH menghalangi balasan chatbot.
- Semua query menggunakan parameter (%s).
- Teks ucapan tidak dikenali dimasking dari PII (nomor telepon, email, deretan angka).
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from db.koneksi import buat_koneksi

logger = logging.getLogger("sigap.db")

_RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_RE_TELEPON = re.compile(r"(?:\+62|62|0)8[0-9\-\s]{7,13}")
_RE_ANGKA_PANJANG = re.compile(r"\b\d{5,}\b")


def masking_teks(teks: str) -> str:
    """Menyamarkan email, nomor telepon, dan deretan angka >= 5 digit untuk privasi."""
    if not isinstance(teks, str):
        return ""
    hasil = _RE_EMAIL.sub("[EMAIL]", teks.strip())
    hasil = _RE_TELEPON.sub("[TELEPON]", hasil)
    hasil = _RE_ANGKA_PANJANG.sub("[ANGKA]", hasil)
    return hasil[:500]


def catat_keputusan(
    conn: Any,
    sesi_id: str,
    keputusan: Any,
    balasan: Any,
    versi_kb: str,
    latensi_ms: int,
    teks_asli: str = "",
) -> None:
    """Mencatat keputusan NLU dan (bila fallback) ucapan tidak dikenali pada koneksi aktif."""
    nlu = keputusan.nlu
    intent_tag: Optional[str] = nlu.terpilih.tag if nlu.terpilih else None
    confidence: Optional[float] = float(nlu.terpilih.confidence) if nlu.terpilih else (
        float(nlu.kandidat[0].confidence) if nlu.kandidat else 0.0
    )
    entity_json = json.dumps(nlu.entity or {}, ensure_ascii=False)
    id_respons = (balasan.id_respons or "")[:20] if balasan and balasan.id_respons else None

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO log_keputusan "
            "(sesi_id, intent, confidence, entity_json, aksi, id_respons, versi_kb, latensi_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(sesi_id)[:32],
                intent_tag,
                confidence,
                entity_json,
                str(keputusan.aksi)[:20],
                id_respons,
                str(versi_kb)[:20],
                int(latensi_ms),
            ),
        )

        if keputusan.aksi == "fallback" and teks_asli and teks_asli.strip():
            teks_aman = masking_teks(teks_asli)
            kandidat_atas = nlu.kandidat[0].tag if nlu.kandidat else None
            conf_atas = float(nlu.kandidat[0].confidence) if nlu.kandidat else 0.0
            cur.execute(
                "INSERT INTO ucapan_tidak_dikenali "
                "(teks_dimasking, kandidat_teratas, confidence, status_tinjau) "
                "VALUES (%s, %s, %s, %s)",
                (teks_aman, kandidat_atas, conf_atas, "baru"),
            )
    conn.commit()


def catat_keputusan_aman(
    sesi_id: str,
    keputusan: Any,
    balasan: Any,
    versi_kb: str,
    latensi_ms: int,
    teks_asli: str = "",
) -> bool:
    """Membuka koneksi dan mencatat log keputusan secara aman tanpa melempar exception."""
    conn = None
    try:
        conn = buat_koneksi()
        catat_keputusan(conn, sesi_id, keputusan, balasan, versi_kb, latensi_ms, teks_asli=teks_asli)
        return True
    except Exception as exc:
        logger.warning("Log MySQL dilewati (database tidak tersedia): %s", exc)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def catat_feedback_aman(sesi_id: str, id_respons: str, nilai: int, versi_kb: str) -> bool:
    """Menyimpan penilaian 👍 (1) atau 👎 (-1) ke tabel feedback secara aman."""
    conn = None
    try:
        nilai_int = 1 if int(nilai) > 0 else -1
        conn = buat_koneksi()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (sesi_id, id_respons, nilai, versi_kb) "
                "VALUES (%s, %s, %s, %s)",
                (str(sesi_id)[:32], str(id_respons)[:20], nilai_int, str(versi_kb)[:20]),
            )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Feedback MySQL dilewati (database tidak tersedia): %s", exc)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def statistik() -> Dict[str, Any]:
    """Mengambil ringkasan statistik untuk halaman /admin."""
    hasil: Dict[str, Any] = {
        "db_tersedia": False,
        "total_pesan": 0,
        "persen_fallback": 0.0,
        "persen_klarifikasi": 0.0,
        "persen_darurat": 0.0,
        "rata_latensi_ms": 0,
        "intent_terbanyak": [],
        "ucapan_baru": [],
        "feedback_ringkasan": [],
    }
    conn = None
    try:
        conn = buat_koneksi()
        hasil["db_tersedia"] = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN aksi = 'fallback' THEN 1 ELSE 0 END) AS jml_fallback, "
                "SUM(CASE WHEN aksi = 'klarifikasi' THEN 1 ELSE 0 END) AS jml_klarifikasi, "
                "SUM(CASE WHEN aksi = 'darurat' THEN 1 ELSE 0 END) AS jml_darurat, "
                "AVG(latensi_ms) AS rata_latensi "
                "FROM log_keputusan"
            )
            row = cur.fetchone() or {}
            total = int(row.get("total") or 0)
            hasil["total_pesan"] = total
            if total > 0:
                hasil["persen_fallback"] = round((int(row.get("jml_fallback") or 0) / total) * 100, 1)
                hasil["persen_klarifikasi"] = round((int(row.get("jml_klarifikasi") or 0) / total) * 100, 1)
                hasil["persen_darurat"] = round((int(row.get("jml_darurat") or 0) / total) * 100, 1)
                hasil["rata_latensi_ms"] = int(round(float(row.get("rata_latensi") or 0)))

            cur.execute(
                "SELECT COALESCE(intent, '(tanpa intent)') AS intent, COUNT(*) AS jumlah "
                "FROM log_keputusan "
                "GROUP BY intent "
                "ORDER BY jumlah DESC "
                "LIMIT 10"
            )
            hasil["intent_terbanyak"] = cur.fetchall() or []

            cur.execute(
                "SELECT id, waktu, teks_dimasking, kandidat_teratas, confidence, status_tinjau "
                "FROM ucapan_tidak_dikenali "
                "WHERE status_tinjau = 'baru' "
                "ORDER BY waktu DESC "
                "LIMIT 25"
            )
            hasil["ucapan_baru"] = cur.fetchall() or []

            cur.execute(
                "SELECT id_respons, "
                "SUM(CASE WHEN nilai = 1 THEN 1 ELSE 0 END) AS positif, "
                "SUM(CASE WHEN nilai = -1 THEN 1 ELSE 0 END) AS negatif "
                "FROM feedback "
                "GROUP BY id_respons "
                "ORDER BY negatif DESC, positif DESC "
                "LIMIT 10"
            )
            hasil["feedback_ringkasan"] = cur.fetchall() or []
    except Exception as exc:
        logger.warning("Gagal mengambil statistik admin dari MySQL: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return hasil

