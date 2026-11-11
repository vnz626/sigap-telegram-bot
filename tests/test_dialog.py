"""Unit test untuk modul core/dialog.py dan core/context.py."""

import config
from kb_loader import muat_kb
from core.engine import Core
from core.model import PesanMasuk, Sesi


def test_klarifikasi_saat_entity_kosong():
    """Kasus Uji Kritis #5: 'gempa' (sendirian) -> klarifikasi, bukan jawaban acak."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    balasan, sesi_baru, keputusan = core.proses(PesanMasuk(teks="gempa", waktu_epoch=100.0), Sesi())
    assert keputusan.aksi == "klarifikasi"
    assert sesi_baru.status == "MENUNGGU_KLARIFIKASI"
    assert sesi_baru.klarifikasi_untuk == "fase"
    assert sesi_baru.bencana_terakhir == "gempa"
    assert len(balasan.tombol) >= 3


def test_fallback_bertahap_setelah_2_kali():
    """FR-09: Fallback bertahap (teks dulu, lalu menu tombol lengkap setelah 2 kali gagal)."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    sesi = Sesi()
    b1, sesi, kep1 = core.proses(PesanMasuk(teks="xyz tidak jelas satu", waktu_epoch=100.0), sesi)
    assert kep1.aksi == "fallback"
    assert sesi.fallback_berturut == 1

    b2, sesi, kep2 = core.proses(PesanMasuk(teks="xyz tidak jelas dua", waktu_epoch=110.0), sesi)
    assert kep2.aksi == "fallback"
    assert sesi.fallback_berturut == 2
    assert "Tips Pencarian Cepat" in b2.teks
    assert any(t.payload.startswith("m:menu_bantuan") for t in b2.tombol)


def test_ttl_sesi_kedaluwarsa_10_menit():
    """Konteks sesi kedaluwarsa setelah > 600 detik tanpa aktivitas."""
    kb = muat_kb(config.KB_PATH)
    core = Core(kb, config.NLU, config.SESI)

    _, sesi_1, _ = core.proses(PesanMasuk(teks="saat gempa", waktu_epoch=1000.0), Sesi())
    assert sesi_1.bencana_terakhir == "gempa"

    # Setelah 700 detik (> 600 detik), konteks gempa sudah kedaluwarsa -> memicu klarifikasi bencana
    _, sesi_2, kep_2 = core.proses(PesanMasuk(teks="kalau sesudahnya?", waktu_epoch=1705.0), sesi_1)
    assert kep_2.aksi == "klarifikasi"
    assert sesi_2.klarifikasi_untuk == "bencana"

