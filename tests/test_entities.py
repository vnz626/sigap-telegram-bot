"""Unit test untuk modul core/entities.py."""

import config
from kb_loader import muat_kb
from core.normalizer import normalisasi
from core.entities import ekstrak_entity, ada_dengan_batas_kata


def test_batas_kata():
    assert ada_dengan_batas_kata("saat", "saat gempa") is True
    assert ada_dengan_batas_kata("saat", "sesaat kemudian") is False
    assert ada_dengan_batas_kata("banjir", "kebanjiran") is False


def test_ekstraksi_bencana_sinonim_dan_typo():
    kb = muat_kb(config.KB_PATH)

    # Sinonim 'lindu' -> gempa
    t1 = normalisasi("pas lindu ngumpet dimana", kb.slang)
    ent1 = ekstrak_entity(t1, kb.entities, config.NLU)
    assert ent1.get("bencana") == "gempa"

    # Typo 'gmpa' -> gempa
    t2 = normalisasi("gmpa gede harus gimana", kb.slang)
    ent2 = ekstrak_entity(t2, kb.entities, config.NLU)
    assert ent2.get("bencana") == "gempa"

    # Sinonim 'air naik' -> banjir
    t3 = normalisasi("air naik terus gimana", kb.slang)
    ent3 = ekstrak_entity(t3, kb.entities, config.NLU)
    assert ent3.get("bencana") == "banjir"

    # Typo fuzzy tanpa slang ('longsoor' / 'lndsor' >= 0.85)
    ent4 = ekstrak_entity("tanda tanah longsr", kb.entities, config.NLU)
    assert ent4.get("bencana") == "longsor"


def test_ekstraksi_situasi_kelompok_dan_istilah():
    kb = muat_kb(config.KB_PATH)

    ent_sit = ekstrak_entity("gimana kalau gempa pas di mobil", kb.entities, config.NLU)
    assert ent_sit.get("bencana") == "gempa"
    assert ent_sit.get("situasi") == "kendaraan"

    ent_kel = ekstrak_entity("kalau buat bayi dan lansia", kb.entities, config.NLU)
    assert ent_kel.get("kelompok") in ("anak_bayi", "lansia")

    ent_ist = ekstrak_entity("bedanya magnitudo sama intensitas", kb.entities, config.NLU)
    assert ent_ist.get("istilah") == "magnitudo"

