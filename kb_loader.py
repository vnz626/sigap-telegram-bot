"""Pemuat dan validator Knowledge Base (JSON) SIGAP beserta mekanisme fallback mode bawaan."""

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from core.fallback_bawaan import buat_kb_bawaan

logger = logging.getLogger("sigap.kb")

BERKAS_WAJIB = (
    "entities.json",
    "intents.json",
    "responses.json",
    "glossary.json",
    "contacts.json",
    "slang.json",
)

BENCANA_P1 = ("gempa", "banjir", "longsor")
FASE_INTENT_P1 = ("info_sebelum", "info_saat", "info_sesudah")


class KnowledgeBase:
    """Representasi di memori untuk Knowledge Base SIGAP yang telah terindeks."""

    def __init__(self, data: Dict[str, Any]):
        self.versi: str = str(data.get("versi", "2.0.0"))
        self.mode_bawaan: bool = bool(data.get("mode_bawaan", False))
        self.slang: Dict[str, str] = data.get("slang", {})
        self.entities: Dict[str, Any] = data.get("entities", {})
        self.intents: List[Dict[str, Any]] = data.get("intents", [])
        self.responses: List[Dict[str, Any]] = data.get("responses", [])
        self.glossary: Dict[str, Any] = data.get("glossary", {})
        self.contacts: Dict[str, Any] = data.get("contacts", {})

        self.intents_map: Dict[str, Dict[str, Any]] = {it["tag"]: it for it in self.intents if "tag" in it}
        self._indeks_respons: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Dict[str, Any]] = {}
        self._indeks_id: Dict[str, Dict[str, Any]] = {}
        self._bangun_indeks()

    def _bangun_indeks(self) -> None:
        for r in self.responses:
            rid = r.get("id")
            if rid:
                self._indeks_id[rid] = r
            intent_tag = r.get("intent", "")
            ent_dict = r.get("entity", {}) or {}
            kunci_ent = tuple(sorted((str(k), str(v)) for k, v in ent_dict.items()))
            self._indeks_respons[(intent_tag, kunci_ent)] = r

    def ambil_respons(self, intent: str, entity: Dict[str, str] | None = None) -> Optional[Dict[str, Any]]:
        """Mencari respons paling spesifik berdasarkan intent dan kombinasi entity."""
        entity = entity or {}

        # 1. Coba kecocokan persis seluruh entity yang relevan
        if intent == "situasi_khusus":
            b = entity.get("bencana")
            s = entity.get("situasi")
            if b and s:
                kunci = tuple(sorted([("bencana", b), ("situasi", s)]))
                if (intent, kunci) in self._indeks_respons:
                    return self._indeks_respons[(intent, kunci)]
            # Fallback jika situasi spesifik untuk bencana tsb belum ada: kembali ke info_saat bencana tsb
            if b:
                kunci_b = (("bencana", b),)
                if ("info_saat", kunci_b) in self._indeks_respons:
                    return self._indeks_respons[("info_saat", kunci_b)]

        if intent == "kelompok_rentan" and "kelompok" in entity:
            kunci = (("kelompok", entity["kelompok"]),)
            if (intent, kunci) in self._indeks_respons:
                return self._indeks_respons[(intent, kunci)]

        if "bencana" in entity:
            kunci = (("bencana", entity["bencana"]),)
            if (intent, kunci) in self._indeks_respons:
                return self._indeks_respons[(intent, kunci)]

        # 2. Coba respons umum tanpa entity untuk intent tersebut
        if (intent, ()) in self._indeks_respons:
            return self._indeks_respons[(intent, ())]

        return None

    def ambil_istilah(self, kode_istilah: str) -> Optional[Dict[str, Any]]:
        return self.glossary.get(kode_istilah)


def _hitung_langkah_bernomor(teks: str) -> int:
    return len(re.findall(r"(?m)^\s*\d+\.\s+", teks))


def validasi_data_kb(
    raw_files: Dict[str, Any],
    tanggal_acuan: Optional[date] = None,
) -> Tuple[List[str], List[str]]:
    """Memvalidasi seluruh aturan keselamatan & integritas KB sesuai Bagian 7.3.

    Mengembalikan: (daftar_error, daftar_peringatan)
    """
    errors: List[str] = []
    warnings: List[str] = []
    hari_ini = tanggal_acuan or date.today()

    # 1. Cek kelengkapan berkas
    for nama in BERKAS_WAJIB:
        if nama not in raw_files or not isinstance(raw_files[nama], dict):
            errors.append(f"Berkas '{nama}' tidak ditemukan atau bukan objek JSON valid.")
    if errors:
        return errors, warnings

    entities_data = raw_files["entities.json"]
    intents_data = raw_files["intents.json"].get("intents")
    responses_data = raw_files["responses.json"].get("responses")
    glossary_data = raw_files["glossary.json"].get("istilah")
    contacts_data = raw_files["contacts.json"].get("nomor_darurat")
    slang_data = raw_files["slang.json"].get("kamus")

    if not isinstance(intents_data, list) or not intents_data:
        errors.append("intents.json harus memiliki array 'intents' yang tidak kosong.")
    if not isinstance(responses_data, list) or not responses_data:
        errors.append("responses.json harus memiliki array 'responses' yang tidak kosong.")
    if not isinstance(glossary_data, dict) or not glossary_data:
        errors.append("glossary.json harus memiliki objek 'istilah' yang tidak kosong.")
    if not isinstance(contacts_data, list) or not contacts_data:
        errors.append("contacts.json harus memiliki array 'nomor_darurat' yang tidak kosong.")
    if not isinstance(slang_data, dict):
        errors.append("slang.json harus memiliki objek 'kamus'.")
    if errors:
        return errors, warnings

    # 2. Validasi intent & duplikasi kata kunci dengan bobot sama di dua intent
    peta_kuat: Dict[str, str] = {}
    peta_pendukung: Dict[str, str] = {}
    daftar_tag_intent = set()

    for idx, it in enumerate(intents_data):
        if not isinstance(it, dict):
            errors.append(f"Intent indeks {idx} bukan objek.")
            continue
        for kolom in ("id", "tag", "prioritas", "entity_wajib", "kuat", "pendukung"):
            if kolom not in it:
                errors.append(f"Intent indeks {idx} kehilangan atribut wajib '{kolom}'.")
        tag = it.get("tag", f"idx_{idx}")
        daftar_tag_intent.add(tag)

        for kw in it.get("kuat", []):
            kw_norm = str(kw).strip().lower()
            if kw_norm in peta_kuat and peta_kuat[kw_norm] != tag:
                errors.append(
                    f"Kata kunci kuat identik '{kw_norm}' ditemukan di dua intent: '{peta_kuat[kw_norm]}' dan '{tag}'."
                )
            peta_kuat[kw_norm] = tag

        for kw in it.get("pendukung", []):
            kw_norm = str(kw).strip().lower()
            if kw_norm in peta_pendukung and peta_pendukung[kw_norm] != tag:
                errors.append(
                    f"Kata kunci pendukung identik '{kw_norm}' ditemukan di dua intent: '{peta_pendukung[kw_norm]}' dan '{tag}'."
                )
            peta_pendukung[kw_norm] = tag

    # 3. Validasi setiap item di responses.json
    id_terpakai = set()
    kombinasi_terisi = set()

    for idx, resp in enumerate(responses_data):
        if not isinstance(resp, dict):
            errors.append(f"Respons indeks {idx} bukan objek.")
            continue

        rid = resp.get("id")
        if not rid or not isinstance(rid, str):
            errors.append(f"Respons indeks {idx} tidak memiliki 'id' valid.")
            rid = f"UNKNOWN_{idx}"
        elif rid in id_terpakai:
            errors.append(f"Duplikasi ID respons: '{rid}'.")
        id_terpakai.add(rid)

        intent_tag = resp.get("intent")
        if intent_tag not in daftar_tag_intent and intent_tag != "fallback":
            errors.append(f"Respons '{rid}' merujuk ke intent yang tidak terdaftar: '{intent_tag}'.")

        ent = resp.get("entity")
        if not isinstance(ent, dict):
            errors.append(f"Respons '{rid}' harus memiliki 'entity' bertipe dict.")
            ent = {}

        if "bencana" in ent:
            kombinasi_terisi.add((intent_tag, ent["bencana"]))
        else:
            kombinasi_terisi.add((intent_tag, None))

        teks = resp.get("teks", "")
        if not isinstance(teks, str) or not teks.strip():
            errors.append(f"Respons '{rid}' memiliki 'teks' kosong.")

        # Aturan keselamatan: fase 'saat' dan 'darurat_aktif' wajib memuat "112" dan <= 6 langkah bernomor
        if intent_tag in ("info_saat", "darurat_aktif"):
            if "112" not in teks:
                errors.append(f"Aturan keselamatan dilanggar: Respons '{rid}' ({intent_tag}) wajib memuat nomor '112'.")
            jml_langkah = _hitung_langkah_bernomor(teks)
            if jml_langkah > 6:
                errors.append(
                    f"Aturan keselamatan dilanggar: Respons '{rid}' memiliki {jml_langkah} langkah bernomor (maksimal 6)."
                )

        # Aturan keselamatan: intent 'prediksi' tidak boleh memuat angka tanggal/jam prediksi
        if intent_tag == "prediksi" and re.search(r"\d", teks):
            errors.append(f"Aturan keselamatan dilanggar: Respons prediksi '{rid}' tidak boleh memuat angka waktu/tanggal.")

        # Wajib bersumber & diverifikasi
        sumber = resp.get("sumber")
        if not isinstance(sumber, list) or len(sumber) == 0:
            errors.append(f"Respons '{rid}' wajib memiliki minimal satu 'sumber'.")
        else:
            for s in sumber:
                if not isinstance(s, dict) or not s.get("nama") or not s.get("url"):
                    errors.append(f"Sumber pada respons '{rid}' wajib memiliki 'nama' dan 'url'.")

        diverifikasi = resp.get("diverifikasi")
        if not diverifikasi or not isinstance(diverifikasi, str):
            errors.append(f"Respons '{rid}' wajib memiliki tanggal 'diverifikasi'.")
        else:
            try:
                date.fromisoformat(diverifikasi)
            except ValueError:
                errors.append(f"Tanggal 'diverifikasi' pada '{rid}' tidak berformat YYYY-MM-DD: '{diverifikasi}'.")

        if not resp.get("diverifikasi_oleh"):
            errors.append(f"Respons '{rid}' wajib memiliki 'diverifikasi_oleh'.")

        kadaluarsa = resp.get("kadaluarsa_tinjau")
        if not kadaluarsa or not isinstance(kadaluarsa, str):
            errors.append(f"Respons '{rid}' wajib memiliki 'kadaluarsa_tinjau'.")
        else:
            try:
                tgl_exp = date.fromisoformat(kadaluarsa)
                if tgl_exp < hari_ini:
                    warnings.append(f"Respons '{rid}' telah melewati kadaluarsa_tinjau ({kadaluarsa}).")
            except ValueError:
                errors.append(f"Tanggal 'kadaluarsa_tinjau' pada '{rid}' tidak berformat YYYY-MM-DD: '{kadaluarsa}'.")

    # 4. Cek matriks cakupan Bencana P1 x Fase P1
    for b in BENCANA_P1:
        if b not in entities_data.get("bencana", {}):
            errors.append(f"Entity bencana wajib P1 '{b}' tidak ditemukan di entities.json.")
        for f_intent in FASE_INTENT_P1:
            if (f_intent, b) not in kombinasi_terisi:
                errors.append(f"Matriks cakupan P1 bolong: belum ada respons untuk intent='{f_intent}', bencana='{b}'.")

    # 5. Cek referensi tombol di setiap respons apakah putus
    kb_sementara = KnowledgeBase(
        {
            "versi": raw_files["responses.json"].get("versi", "2.0.0"),
            "slang": slang_data,
            "entities": entities_data,
            "intents": intents_data,
            "responses": responses_data,
            "glossary": glossary_data,
            "contacts": raw_files["contacts.json"],
        }
    )
    for resp in responses_data:
        rid = resp.get("id", "?")
        for spek_tombol in resp.get("tombol", []):
            bagian = str(spek_tombol).split(":")
            it_tag = bagian[0]
            ent1 = bagian[1] if len(bagian) > 1 else ""
            ent2 = bagian[2] if len(bagian) > 2 else ""

            if it_tag == "definisi_istilah" and ent1:
                if not kb_sementara.ambil_istilah(ent1):
                    errors.append(f"Referensi tombol putus pada '{rid}': istilah '{ent1}' tidak ada di glossary.json.")
                continue

            ent_uji: Dict[str, str] = {}
            if it_tag == "kelompok_rentan" and ent1:
                ent_uji["kelompok"] = ent1
            elif ent1:
                ent_uji["bencana"] = ent1
            if ent2:
                ent_uji["situasi"] = ent2

            if not kb_sementara.ambil_respons(it_tag, ent_uji):
                errors.append(f"Referensi tombol putus pada '{rid}': target '{spek_tombol}' tidak memiliki respons.")

    return errors, warnings


def muat_kb(kb_dir: str | Path) -> KnowledgeBase:
    """Memuat dan memvalidasi berkas JSON dari direktori kb_dir. Melempar ValueError bila tidak valid."""
    jalur = Path(kb_dir)
    raw_files: Dict[str, Any] = {}

    for nama in BERKAS_WAJIB:
        berkas = jalur / nama
        if not berkas.is_file():
            raise ValueError(f"Berkas KB tidak ditemukan: {berkas}")
        with open(berkas, "r", encoding="utf-8") as f:
            raw_files[nama] = json.load(f)

    errors, warnings = validasi_data_kb(raw_files)
    for w in warnings:
        logger.warning("Peringatan KB: %s", w)
    if errors:
        raise ValueError("Validasi KB gagal:\n- " + "\n- ".join(errors))

    return KnowledgeBase(
        {
            "versi": raw_files["responses.json"].get("versi", "2.0.0"),
            "mode_bawaan": False,
            "slang": raw_files["slang.json"].get("kamus", {}),
            "entities": raw_files["entities.json"],
            "intents": raw_files["intents.json"].get("intents", []),
            "responses": raw_files["responses.json"].get("responses", []),
            "glossary": raw_files["glossary.json"].get("istilah", {}),
            "contacts": raw_files["contacts.json"],
        }
    )


def muat_atau_bawaan(kb_dir: str | Path) -> Tuple[KnowledgeBase, bool]:
    """Memuat KB dari disk; jika gagal/rusak, mengembalikan KB mode bawaan darurat (Bagian 7.4)."""
    try:
        kb = muat_kb(kb_dir)
        return kb, False
    except Exception as exc:
        logger.error("Gagal memuat Knowledge Base utama (%s). Mengaktifkan MODE BAWAAN DARURAT.", exc)
        kb_cadangan = KnowledgeBase(buat_kb_bawaan())
        return kb_cadangan, True

