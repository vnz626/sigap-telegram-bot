"""Unit test untuk modul core/intents.py (skoring confidence & deteksi ambiguitas)."""

import config
from kb_loader import muat_kb
from core.intents import skor_intent, cocok


def test_cocok_batas_kata_dan_fuzzy():
    # Persis -> 1.0
    assert cocok("saat", "saat banjir", ambang=0.85) == 1.0
    # "saat" tidak boleh cocok dengan "sesaat"
    assert cocok("saat", "sesaat kemudian", ambang=0.85) == 0.0
    # Fuzzy untuk kata >= 4 huruf ("persiapan" vs "persiapaan")
    assert cocok("persiapan", "persiapaan gempa", ambang=0.85) >= 0.85


def test_skoring_ambang_tepat_050():
    """Kasus Uji Kritis #7: 'saat banjir' -> confidence 0.50, lolos tepat di ambang."""
    kb = muat_kb(config.KB_PATH)
    _, terpilih, ambigu = skor_intent("saat banjir", kb.intents, config.NLU)
    assert terpilih is not None
    assert terpilih.tag == "info_saat"
    assert terpilih.confidence == 0.50
    assert ambigu is False


def test_skoring_situasi_khusus_067():
    """Kasus Uji Kritis #6: 'gimana kalau gempa pas di mobil' -> situasi_khusus, confidence 0.67."""
    kb = muat_kb(config.KB_PATH)
    _, terpilih, ambigu = skor_intent("gimana kalau gempa pas di mobil", kb.intents, config.NLU)
    assert terpilih is not None
    assert terpilih.tag == "situasi_khusus"
    assert terpilih.confidence == 0.67
    assert ambigu is False


def test_deteksi_intent_ambigu():
    """Jika dua intent memiliki prioritas sama dan selisih confidence < 0.15, ditandai ambigu."""
    intents_uji = [
        {"tag": "intent_a", "prioritas": 1, "kuat": ["kata satu"], "pendukung": []},
        {"tag": "intent_b", "prioritas": 1, "kuat": ["kata dua"], "pendukung": []},
    ]
    _, terpilih, ambigu = skor_intent("kata satu dan kata dua", intents_uji, config.NLU)
    assert terpilih is not None
    assert ambigu is True

