"""Unit test untuk modul core/normalizer.py."""

from core.normalizer import normalisasi, bersihkan_karakter_kontrol


def test_lowercase_dan_tanda_baca():
    assert normalisasi("Halo! Apa kabar??") == "halo apa kabar"
    assert normalisasi("SAAT GEMPA... Harus Gimana?!") == "saat gempa harus gimana"


def test_pertahankan_kata_ulang():
    assert normalisasi("Tips jaga-jaga & siap-siap!") == "tips jaga-jaga siap-siap"
    assert normalisasi("Tanda-tanda longsor apa-apa?") == "tanda-tanda longsor apa-apa"


def test_huruf_berulang_diringkas():
    assert normalisasi("gempaaaa gedeee toloooong") == "gempa gede tolong"


def test_kamus_slang():
    kamus = {
        "gmn": "gimana",
        "gmpa": "gempa",
        "ga": "nggak",
        "udh": "udah",
        "klo": "kalau",
    }
    assert normalisasi("klo gmpa gmn ya? udh reda ga?", kamus) == "kalau gempa gimana ya udah reda nggak"


def test_karakter_kontrol_dan_input_kosong():
    assert bersihkan_karakter_kontrol("halo\x00\x07dunia").strip() == "halo dunia"
    assert normalisasi("") == ""
    assert normalisasi("   ??? !!!   ") == ""
    assert normalisasi("😀👍🔥") == ""

