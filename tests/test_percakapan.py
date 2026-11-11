"""Pengujian skenario percakapan multi-giliran, 13 Kasus Uji Kritis (Bagian 13.2), dan API Flask."""

import ast
import re
from pathlib import Path
from unittest.mock import patch

import config
from app import buat_app
from kb_loader import muat_kb
from core.engine import Core
from core.model import PesanMasuk, Sesi
from web.formatter import ke_html


# ============================================================================
# 1. Pengujian Arsitektur: Core Murni (Bagian 4.3 & 5)
# ============================================================================
def test_core_bebas_dependensi_web_dan_db():
    """Memastikan seluruh berkas di core/ tidak mengimpor flask, pymysql, os.environ, atau time.time."""
    core_dir = Path(config.BASE_DIR) / "core"
    terlarang_modul = {"flask", "pymysql", "db", "web"}

    for py_file in core_dir.glob("*.py"):
        isi = py_file.read_text(encoding="utf-8")
        pohon = ast.parse(isi, filename=str(py_file))
        for simpul in ast.walk(pohon):
            if isinstance(simpul, ast.Import):
                for alias in simpul.names:
                    akar = alias.name.split(".")[0]
                    assert akar not in terlarang_modul, f"{py_file.name} mengimpor modul terlarang: {alias.name}"
            elif isinstance(simpul, ast.ImportFrom) and simpul.module:
                akar = simpul.module.split(".")[0]
                assert akar not in terlarang_modul, f"{py_file.name} mengimpor modul terlarang: {simpul.module}"
        assert "os.environ" not in isi, f"{py_file.name} tidak boleh membaca os.environ"
        assert "time.time(" not in isi, f"{py_file.name} tidak boleh memanggil time.time()"


# ============================================================================
# 2. 13 Kasus Uji Kritis Wajib Hijau (Bagian 13.2)
# ============================================================================
def test_kritis_01_tolong_terjebak_banjir():
    """#1: 'tolong terjebak banjir' -> darurat, ada 112, <= 6 baris."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    balasan, _, keputusan = core.proses(PesanMasuk(teks="tolong terjebak banjir", waktu_epoch=100.0), Sesi())
    assert keputusan.aksi == "darurat"
    assert balasan.darurat is True
    assert "112" in balasan.teks
    baris = [b for b in balasan.teks.splitlines() if b.strip()]
    assert len(baris) <= 6


def test_kritis_02_kapan_gempa_besar_terjadi():
    """#2: 'kapan gempa besar terjadi' -> prediksi (tolak sopan), tidak ada tanggal/angka waktu."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    balasan, _, keputusan = core.proses(PesanMasuk(teks="kapan gempa besar terjadi", waktu_epoch=100.0), Sesi())
    assert keputusan.nlu.terpilih is not None
    assert keputusan.nlu.terpilih.tag == "prediksi"
    assert keputusan.aksi == "tolak"
    assert re.search(r"\d", balasan.teks) is None


def test_kritis_03_gmpa_gede_harus_gimana():
    """#3: 'gmpa gede harus gimana' -> entity gempa, intent info_saat."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    _, _, keputusan = core.proses(PesanMasuk(teks="gmpa gede harus gimana", waktu_epoch=100.0), Sesi())
    assert keputusan.nlu.entity.get("bencana") == "gempa"
    assert keputusan.nlu.terpilih is not None
    assert keputusan.nlu.terpilih.tag == "info_saat"


def test_kritis_04_konteks_saat_gempa_lalu_sesudahnya():
    """#4: 'saat gempa' -> 'kalau sesudahnya?' -> info_sesudah + gempa dari konteks."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    _, sesi_1, kep_1 = core.proses(PesanMasuk(teks="saat gempa", waktu_epoch=100.0), Sesi())
    assert kep_1.nlu.terpilih.tag == "info_saat"
    assert sesi_1.bencana_terakhir == "gempa"

    balasan_2, _, kep_2 = core.proses(PesanMasuk(teks="kalau sesudahnya?", waktu_epoch=120.0), sesi_1)
    assert kep_2.aksi == "jawab"
    assert kep_2.nlu.terpilih.tag == "info_sesudah"
    assert kep_2.nlu.entity.get("bencana") == "gempa"
    assert balasan_2.id_respons == "RSP-G3"


def test_kritis_05_gempa_sendirian_klarifikasi():
    """#5: 'gempa' (sendirian) -> klarifikasi, bukan jawaban acak."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    _, sesi_1, kep_1 = core.proses(PesanMasuk(teks="gempa", waktu_epoch=100.0), Sesi())
    assert kep_1.aksi == "klarifikasi"
    assert sesi_1.status == "MENUNGGU_KLARIFIKASI"

    # Pengguna menjawab klarifikasi dengan mengetik "saat"
    balasan_2, sesi_2, kep_2 = core.proses(PesanMasuk(teks="saat", waktu_epoch=115.0), sesi_1)
    assert kep_2.aksi == "jawab"
    assert kep_2.nlu.terpilih.tag == "info_saat"
    assert kep_2.nlu.entity.get("bencana") == "gempa"
    assert balasan_2.id_respons == "RSP-G2"
    assert sesi_2.status == "IDLE"


def test_kritis_06_situasi_khusus_di_mobil_067():
    """#6: 'gimana kalau gempa pas di mobil' -> situasi_khusus, confidence 0.67."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    balasan, _, keputusan = core.proses(
        PesanMasuk(teks="gimana kalau gempa pas di mobil", waktu_epoch=100.0), Sesi()
    )
    assert keputusan.nlu.terpilih.tag == "situasi_khusus"
    assert keputusan.nlu.terpilih.confidence == 0.67
    assert balasan.id_respons == "RSP-G6a"


def test_kritis_07_saat_banjir_ambang_050():
    """#7: 'saat banjir' -> confidence 0.50, lolos tepat di ambang."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)
    balasan, _, keputusan = core.proses(PesanMasuk(teks="saat banjir", waktu_epoch=100.0), Sesi())
    assert keputusan.nlu.terpilih.tag == "info_saat"
    assert keputusan.nlu.terpilih.confidence == 0.50
    assert balasan.id_respons == "RSP-B2"


def test_kritis_08_pesan_kosong_dan_emoji_saja():
    """#8: Pesan kosong, emoji saja -> balasan ramah, tidak crash."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    b_kosong, _, _ = core.proses(PesanMasuk(teks="", waktu_epoch=100.0), Sesi())
    assert isinstance(b_kosong.teks, str) and len(b_kosong.teks) > 0

    b_emoji, _, _ = core.proses(PesanMasuk(teks="😀🙏🌊", waktu_epoch=100.0), Sesi())
    assert isinstance(b_emoji.teks, str) and len(b_emoji.teks) > 0

    # Via Flask API untuk emoji saja
    client = buat_app(aktifkan_batas_laju=False).test_client()
    resp = client.post("/api/chat", json={"pesan": "😀👍"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "balasan" in data and data["balasan"]["html"]


def test_kritis_09_pesan_5000_karakter_ditolak_413():
    """#9: Pesan 5.000 karakter -> ditolak 413."""
    client = buat_app(aktifkan_batas_laju=False).test_client()
    resp = client.post("/api/chat", json={"pesan": "a" * 5000})
    assert resp.status_code == 413
    assert "terlalu panjang" in resp.get_json()["error"].lower()


def test_kritis_10_kb_rusak_masuk_mode_bawaan(tmp_path):
    """#10: KB sengaja dirusak -> mode bawaan aktif, 112 tetap muncul."""
    kb_rusak_dir = tmp_path / "kb_rusak"
    kb_rusak_dir.mkdir()
    (kb_rusak_dir / "entities.json").write_text("{json rusak tidak valid", encoding="utf-8")

    app_bawaan = buat_app(kb_path=kb_rusak_dir, aktifkan_batas_laju=False)
    assert app_bawaan.config["SIGAP_MODE_BAWAAN"] is True

    client = app_bawaan.test_client()
    resp = client.post("/api/chat", json={"pesan": "saat gempa harus gimana"})
    assert resp.status_code == 200
    html_balasan = resp.get_json()["balasan"]["html"]
    assert "112" in html_balasan


def test_kritis_11_mysql_dimatikan_chatbot_tetap_menjawab():
    """#11: MySQL dimatikan -> chatbot tetap menjawab, /health melaporkan DB tidak tersedia."""
    app_uji = buat_app(aktifkan_batas_laju=False)
    client = app_uji.test_client()

    with patch("db.koneksi.pymysql.connect", side_effect= RuntimeError("MySQL sengaja dimatikan")):
        resp_chat = client.post("/api/chat", json={"pesan": "saat gempa"})
        assert resp_chat.status_code == 200
        assert "112" in resp_chat.get_json()["balasan"]["html"]

        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.get_json()["db"] == "tidak tersedia"


def test_kritis_12_teks_kb_berisi_script_diescape():
    """#12: Teks KB berisi <script> -> tampil sebagai teks (&lt;script&gt;), tidak dieksekusi."""
    teks_berbahaya = "Langkah aman:\n1. Jangan panik <script>alert('xss')</script>\n\nHubungi **112**."
    hasil_html = ke_html(teks_berbahaya)
    assert "<script>" not in hasil_html
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in hasil_html
    assert "<strong>112</strong>" in hasil_html


def test_kritis_13_teks_pengguna_berisi_tag_html_aman():
    """#13: Teks pengguna berisi <b>halo</b> -> diproses aman dan chat.js memakai textContent."""
    chat_js = (Path(config.BASE_DIR) / "web" / "static" / "chat.js").read_text(encoding="utf-8")
    assert "bubble.textContent = teks" in chat_js

    client = buat_app(aktifkan_batas_laju=False).test_client()
    resp = client.post("/api/chat", json={"pesan": "<b>halo</b>"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "<b>halo</b>" not in data["balasan"]["html"]


# ============================================================================
# 3. Pengujian Skenario Percakapan Lanjutan & Endpoint Lainnya
# ============================================================================
def test_percakapan_multi_giliran_lengkap():
    """Menguji skenario PDF K.INT-91 (a, b, c, d) dan tombol payload."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    # Skenario c: "tas siaga apa aja?" -> "kalau buat bayi?"
    b1, s1, k1 = core.proses(PesanMasuk(teks="tas siaga apa aja?", waktu_epoch=100.0), Sesi())
    assert k1.nlu.terpilih.tag == "tas_siaga"
    assert b1.id_respons == "RSP-C1"

    b2, s2, k2 = core.proses(PesanMasuk(teks="kalau buat bayi?", waktu_epoch=110.0), s1)
    assert k2.nlu.terpilih.tag == "kelompok_rentan"
    assert k2.nlu.entity.get("kelompok") == "anak_bayi"
    assert b2.id_respons == "RSP-KR-ANAK"

    # Skenario d: "tanda longsor?" -> "terus harus lari kemana?"
    b3, s3, k3 = core.proses(PesanMasuk(teks="tanda longsor?", waktu_epoch=200.0), Sesi())
    assert k3.nlu.terpilih.tag == "tanda_peringatan"
    assert s3.bencana_terakhir == "longsor"

    b4, s4, k4 = core.proses(PesanMasuk(teks="terus harus lari kemana?", waktu_epoch=210.0), s3)
    assert k4.nlu.terpilih.tag == "jalur_evakuasi"
    assert k4.nlu.entity.get("bencana") == "longsor"
    assert b4.id_respons == "RSP-C3"

    # Klik tombol navigasi m:situasi_khusus:gempa:kendaraan
    b5, _, k5 = core.proses(
        PesanMasuk(teks="m:situasi_khusus:gempa:kendaraan", adalah_tombol=True, waktu_epoch=220.0), s4
    )
    assert k5.aksi == "jawab"
    assert b5.id_respons == "RSP-G6a"


def test_endpoint_web_mulai_reset_feedback_dan_admin():
    client = buat_app(aktifkan_batas_laju=False).test_client()

    r_index = client.get("/")
    assert r_index.status_code == 200
    assert b"SIGAP" in r_index.data

    r_mulai = client.get("/api/mulai")
    assert r_mulai.status_code == 200
    assert r_mulai.get_json()["id_respons"] == "RSP-U1"

    r_reset = client.post("/api/reset")
    assert r_reset.status_code == 200
    assert r_reset.get_json()["id_respons"] == "RSP-U1"

    r_fb = client.post("/api/feedback", json={"id_respons": "RSP-G2", "nilai": 1})
    assert r_fb.status_code == 200
    assert r_fb.get_json()["ok"] is True

