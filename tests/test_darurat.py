"""Unit test khusus jalur darurat aktif (Prioritas P0 — target deteksi 100%)."""

import config
from kb_loader import muat_kb
from core.engine import Core
from core.model import PesanMasuk, Sesi


KASUS_DARURAT_WAJIB = [
    "tolong terjebak banjir",
    "tolong aku terjebak banjir",
    "ada yang tertimbun longsor",
    "lagi gempa sekarang",
    "sos air udah naik sepinggang",
    "keluargaku nggak ketemu setelah gempa",
]


def test_deteksi_darurat_100_persen():
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    for kalimat in KASUS_DARURAT_WAJIB:
        balasan, sesi_baru, keputusan = core.proses(PesanMasuk(teks=kalimat, waktu_epoch=500.0), Sesi())
        assert keputusan.aksi == "darurat", f"Gagal mendeteksi darurat pada: {kalimat}"
        assert keputusan.nlu.darurat is True
        assert balasan.darurat is True
        assert "112" in balasan.teks
        assert sesi_baru.status == "MODE_DARURAT"
        # Maksimal 6 baris agar mudah dibaca saat panik (Kasus Uji Kritis #1)
        baris_aktif = [b for b in balasan.teks.splitlines() if b.strip()]
        assert len(baris_aktif) <= 6, f"Balasan darurat terlalu panjang ({len(baris_aktif)} baris)"


def test_non_darurat_tidak_salah_deteksi():
    """Pertanyaan informasi seperti 'terjebak di lift pas gempa' atau 'minta tolong ke mana' bukan darurat aktif."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    _, _, kep1 = core.proses(PesanMasuk(teks="terjebak di lift pas gempa", waktu_epoch=500.0), Sesi())
    assert kep1.aksi == "jawab"
    assert kep1.nlu.terpilih.tag == "situasi_khusus"

    _, _, kep2 = core.proses(PesanMasuk(teks="minta tolong ke mana kalau ada longsor", waktu_epoch=500.0), Sesi())
    assert kep2.aksi == "jawab"
    assert kep2.nlu.terpilih.tag == "kontak_darurat"

