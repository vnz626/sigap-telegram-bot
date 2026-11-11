"""Response Builder SIGAP: menyusun teks balasan, catatan sumber, dan tombol cepat."""

from typing import Dict, Any, List
from core.model import Balasan, Tombol, Sesi, Keputusan

_LABEL_BENCANA = {
    "gempa": "Gempa Bumi",
    "banjir": "Banjir",
    "longsor": "Tanah Longsor",
    "tsunami": "Tsunami",
    "gunung_api": "Gunung Api",
    "angin_kencang": "Angin Kencang",
}

_LABEL_INTENT = {
    "info_sebelum": "Persiapan Sebelum",
    "info_saat": "Saat Terjadi",
    "info_sesudah": "Sesudah",
    "tanda_peringatan": "Tanda Peringatan",
    "situasi_khusus": "Situasi Khusus",
    "penyebab": "Penyebab",
    "kelompok_rentan": "Kelompok Rentan",
    "tas_siaga": "Tas Siaga",
    "kontak_darurat": "Kontak Darurat",
    "jalur_evakuasi": "Jalur Evakuasi",
    "rencana_keluarga": "Rencana Keluarga",
    "sumber_resmi": "Sumber Resmi",
    "definisi_istilah": "Definisi Istilah",
    "mitos_hoaks": "Mitos vs Fakta",
    "cek_gempa_terbaru": "Info Gempa Terkini",
    "prediksi": "Prediksi Bencana",
    "menu_bantuan": "Menu Bantuan",
}

_LABEL_SITUASI = {
    "kendaraan": "Di Kendaraan",
    "gedung_tinggi": "Di Gedung/Lift",
    "sekolah_kampus": "Di Sekolah/Kampus",
    "pesisir": "Di Pesisir",
    "luar_ruangan": "Di Luar Ruangan",
    "rumah": "Di Rumah",
    "lereng_gunung": "Di Lereng/Gunung",
}

_LABEL_KELOMPOK = {
    "anak_bayi": "Anak & Bayi",
    "lansia": "Lansia",
    "difabel": "Difabel / Kursi Roda",
    "ibu_hamil": "Ibu Hamil",
    "hewan_peliharaan": "Hewan Peliharaan",
}


def _buat_tombol_dari_spek(spek: str) -> Tombol:
    """Mengubah string spesifikasi tombol di KB (mis. 'info_sesudah:gempa') menjadi objek Tombol."""
    bagian = spek.split(":")
    intent_tag = bagian[0]
    ent1 = bagian[1] if len(bagian) > 1 else ""
    ent2 = bagian[2] if len(bagian) > 2 else ""

    if intent_tag == "situasi_khusus" and ent1 and ent2:
        label_sit = _LABEL_SITUASI.get(ent2, ent2.replace("_", " ").title())
        return Tombol(label=label_sit, payload=f"m:situasi_khusus:{ent1}:{ent2}")

    if intent_tag == "kelompok_rentan" and ent1:
        label_kel = _LABEL_KELOMPOK.get(ent1, ent1.replace("_", " ").title())
        return Tombol(label=f"Panduan {label_kel}", payload=f"m:kelompok_rentan:{ent1}")

    if intent_tag == "definisi_istilah" and ent1:
        label_ist = ent1.replace("_", " ").title()
        return Tombol(label=f"Arti {label_ist}", payload=f"m:definisi_istilah:{ent1}")

    if ent1:
        nama_bencana = _LABEL_BENCANA.get(ent1, ent1.title())
        if intent_tag == "info_saat":
            label = f"Saat {nama_bencana}"
        elif intent_tag == "info_sebelum":
            label = f"Sebelum {nama_bencana}"
        elif intent_tag == "info_sesudah":
            label = f"Sesudah {nama_bencana}"
        elif intent_tag == "tanda_peringatan":
            label = f"Tanda {nama_bencana}"
        else:
            label = f"{_LABEL_INTENT.get(intent_tag, intent_tag)} {nama_bencana}"
        return Tombol(label=label, payload=f"m:{intent_tag}:{ent1}")

    label = _LABEL_INTENT.get(intent_tag, intent_tag.replace("_", " ").title())
    return Tombol(label=label, payload=f"m:{intent_tag}:")


def _format_teks_dengan_sumber(resp: Dict[str, Any], darurat: bool = False) -> str:
    """Menambahkan baris sumber resmi pada teks respons (kecuali jika darurat agar tetap <= 6 baris)."""
    teks = resp.get("teks", "").strip()
    if darurat:
        return teks

    sumber_list = resp.get("sumber", [])
    if sumber_list:
        nama_sumber = ", ".join(s.get("nama", "") for s in sumber_list if s.get("nama"))
        if nama_sumber and f"Sumber: {nama_sumber}" not in teks:
            teks = f"{teks}\n\nSumber: {nama_sumber}"
    return teks


def bangun_balasan_klarifikasi(keputusan: Keputusan, sesi: Sesi) -> Balasan:
    """Menyusun pertanyaan klarifikasi beserta daftar pilihan tertulis yang jelas."""
    target = sesi.klarifikasi_untuk
    entity = keputusan.nlu.entity
    bencana = entity.get("bencana") or sesi.bencana_terakhir

    if target == "fase" and bencana:
        nama = _LABEL_BENCANA.get(bencana, bencana.title())
        teks = (
            f"Kamu ingin mengetahui informasi **{nama}** pada tahap apa? Silakan ketik salah satu pilihan atau angkanya:\n"
            f"1. **Sebelum {nama}** (persiapan & pencegahan)\n"
            f"2. **Saat {nama}** (langkah penyelamatan diri)\n"
            f"3. **Sesudah {nama}** (pemulihan & pembersihan)\n"
            f"4. **Tanda {nama}** (ciri peringatan dini)\n"
            f"5. **Penyebab {nama}**"
        )
        tombol = [
            Tombol(label=f"Sebelum {nama}", payload=f"k:info_sebelum:{bencana}"),
            Tombol(label=f"Saat {nama}", payload=f"k:info_saat:{bencana}"),
            Tombol(label=f"Sesudah {nama}", payload=f"k:info_sesudah:{bencana}"),
            Tombol(label=f"Tanda {nama}", payload=f"k:tanda_peringatan:{bencana}"),
        ]
        return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-FASE", darurat=False)

    if target == "bencana":
        intent_akt = sesi.intent_terakhir or (keputusan.nlu.terpilih.tag if keputusan.nlu.terpilih else "info_saat")
        label_it = _LABEL_INTENT.get(intent_akt, "panduan")
        teks = (
            f"Untuk **{label_it.lower()}**, bencana apa yang kamu maksud? Silakan ketik nama bencana atau angkanya:\n"
            "1. **Gempa Bumi**\n"
            "2. **Banjir**\n"
            "3. **Tanah Longsor**"
        )
        tombol = [
            Tombol(label="Gempa Bumi", payload=f"k:{intent_akt}:gempa"),
            Tombol(label="Banjir", payload=f"k:{intent_akt}:banjir"),
            Tombol(label="Tanah Longsor", payload=f"k:{intent_akt}:longsor"),
        ]
        return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-BENCANA", darurat=False)

    if target == "situasi":
        bencana_akt = bencana or "gempa"
        nama = _LABEL_BENCANA.get(bencana_akt, bencana_akt.title())
        if bencana_akt == "gempa":
            teks = (
                f"Saat terjadi **{nama}**, kamu sedang berada di situasi atau lokasi mana? Silakan ketik lokasinya atau angkanya:\n"
                "1. **Di kendaraan / mobil**\n"
                "2. **Di gedung bertingkat / lift**\n"
                "3. **Di sekolah / kampus / kos**\n"
                "4. **Di pesisir pantai**\n"
                "5. **Di luar ruangan**\n"
                "6. **Di dalam rumah**"
            )
            tombol = [
                Tombol(label="Di Kendaraan", payload="k:situasi_khusus:gempa:kendaraan"),
                Tombol(label="Di Gedung / Lift", payload="k:situasi_khusus:gempa:gedung_tinggi"),
                Tombol(label="Di Sekolah / Kos", payload="k:situasi_khusus:gempa:sekolah_kampus"),
                Tombol(label="Di Pesisir Pantai", payload="k:situasi_khusus:gempa:pesisir"),
                Tombol(label="Di Luar Ruangan", payload="k:situasi_khusus:gempa:luar_ruangan"),
            ]
        elif bencana_akt == "banjir":
            teks = (
                f"Saat terjadi **{nama}**, kamu sedang berada di situasi mana? Silakan ketik lokasinya atau angkanya:\n"
                "1. **Di kendaraan / mobil**\n"
                "2. **Di dalam rumah**\n"
                "3. **Di dekat aliran sungai**"
            )
            tombol = [
                Tombol(label="Di Kendaraan", payload="k:situasi_khusus:banjir:kendaraan"),
                Tombol(label="Di Rumah", payload="k:situasi_khusus:banjir:rumah"),
                Tombol(label="Dekat Sungai", payload="k:situasi_khusus:banjir:lereng_gunung"),
            ]
        else:
            teks = (
                f"Saat terjadi **{nama}**, kamu sedang berada di situasi mana? Silakan ketik lokasinya atau angkanya:\n"
                "1. **Di lereng / gunung / pendakian**\n"
                "2. **Di rumah dekat lereng**\n"
                "3. **Di jalan raya / kendaraan**"
            )
            tombol = [
                Tombol(label="Di Lereng / Gunung", payload="k:situasi_khusus:longsor:lereng_gunung"),
                Tombol(label="Di Rumah Dekat Lereng", payload="k:situasi_khusus:longsor:rumah"),
            ]
        return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-SITUASI", darurat=False)

    if target == "kelompok":
        teks = (
            "Panduan kesiapsiagaan kelompok rentan mana yang ingin kamu ketahui? Silakan ketik pilihannya atau angkanya:\n"
            "1. **Anak & Bayi**\n"
            "2. **Lansia**\n"
            "3. **Difabel / Kursi Roda**\n"
            "4. **Ibu Hamil**\n"
            "5. **Hewan Peliharaan**"
        )
        tombol = [
            Tombol(label="Anak & Bayi", payload="m:kelompok_rentan:anak_bayi"),
            Tombol(label="Lansia", payload="m:kelompok_rentan:lansia"),
            Tombol(label="Difabel / Kursi Roda", payload="m:kelompok_rentan:difabel"),
            Tombol(label="Ibu Hamil", payload="m:kelompok_rentan:ibu_hamil"),
        ]
        return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-KELOMPOK", darurat=False)

    if target == "istilah":
        teks = (
            "Istilah kebencanaan apa yang ingin kamu ketahui artinya? Silakan ketik salah satu istilah berikut:\n"
            "1. **Magnitudo** (atau bedanya dengan **Intensitas**)\n"
            "2. **Megathrust**\n"
            "3. **Episenter** / **Hiposenter**\n"
            "4. **Status Gunung Api** (Normal, Waspada, Siaga, Awas)\n"
            "5. **Mitigasi** / **Tas Siaga** / **Jalur Evakuasi**"
        )
        tombol = [
            Tombol(label="Magnitudo vs Intensitas", payload="m:definisi_istilah:magnitudo"),
            Tombol(label="Megathrust", payload="m:definisi_istilah:megathrust"),
            Tombol(label="Status Gunung Api", payload="m:definisi_istilah:status_gunung_api"),
            Tombol(label="Mitigasi", payload="m:definisi_istilah:mitigasi"),
        ]
        return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-ISTILAH", darurat=False)

    # Klarifikasi intent ambigu
    kandidat = [k for k in keputusan.nlu.kandidat if k.tag != "lanjutan"][:2]
    baris_opsi = []
    tombol: List[Tombol] = []
    for idx, k in enumerate(kandidat, start=1):
        label = _LABEL_INTENT.get(k.tag, k.tag.replace("_", " ").title())
        if bencana:
            nama_b = _LABEL_BENCANA.get(bencana, bencana.title())
            baris_opsi.append(f"{idx}. **{label} ({nama_b})**")
            tombol.append(Tombol(label=f"{label} ({nama_b})", payload=f"m:{k.tag}:{bencana}"))
        else:
            baris_opsi.append(f"{idx}. **{label}**")
            tombol.append(Tombol(label=label, payload=f"m:{k.tag}:"))
    teks = "Pertanyaanmu bisa merujuk ke beberapa topik. Silakan ketik salah satu yang kamu maksud:\n" + "\n".join(baris_opsi)
    return Balasan(teks=teks, tombol=tombol, id_respons="KLARIFIKASI-INTENT", darurat=False)


def bangun_balasan(
    keputusan: Keputusan,
    sesi: Sesi,
    kb: Any,
    cfg_sesi: Dict[str, Any] | None = None,
) -> Balasan:
    """Menyusun objek Balasan akhir dari Keputusan NLU/Dialog dan KnowledgeBase."""
    cfg_sesi = cfg_sesi or {}
    batas_fallback_menu = int(cfg_sesi.get("fallback_sebelum_menu", 2))

    aksi = keputusan.aksi
    entity = keputusan.nlu.entity
    terpilih = keputusan.nlu.terpilih

    # 1. Klarifikasi
    if aksi == "klarifikasi":
        return bangun_balasan_klarifikasi(keputusan, sesi)

    # 2. Darurat Aktif
    if aksi == "darurat":
        resp = kb.ambil_respons("darurat_aktif", entity)
        if not resp:
            resp = kb.ambil_respons("darurat_aktif", {})
        tombol = [_buat_tombol_dari_spek(s) for s in resp.get("tombol", ["kontak_darurat"])]
        return Balasan(
            teks=_format_teks_dengan_sumber(resp, darurat=True),
            tombol=tombol,
            id_respons=resp.get("id", "RSP-E1"),
            darurat=True,
        )

    # 3. Fallback bertahap (FR-09: teks dulu, lalu menu tombol lengkap setelah >= 2 kali gagal)
    if aksi == "fallback":
        resp = kb.ambil_respons("fallback", {})
        teks_dasar = resp.get(
            "teks",
            "Maaf, aku belum paham. Coba tanyakan soal gempa, banjir, atau longsor, atau pilih menu bantuan di bawah.",
        )
        if sesi.fallback_berturut >= batas_fallback_menu:
            teks_dasar += (
                "\n\n**Tips Pencarian Cepat:**\n"
                "1. Gunakan kata kunci singkat seperti **\"saat gempa\"**, **\"sebelum banjir\"**, atau **\"tanda longsor\"**.\n"
                "2. Atau tekan langsung salah satu tombol menu utama di bawah ini:"
            )
            tombol = [
                Tombol(label="Menu Bantuan Lengkap", payload="m:menu_bantuan:"),
                Tombol(label="Saat Gempa", payload="m:info_saat:gempa"),
                Tombol(label="Saat Banjir", payload="m:info_saat:banjir"),
                Tombol(label="Saat Longsor", payload="m:info_saat:longsor"),
                Tombol(label="Tas Siaga", payload="m:tas_siaga:"),
                Tombol(label="Kontak Darurat 112", payload="m:kontak_darurat:"),
            ]
        else:
            tombol = [_buat_tombol_dari_spek(s) for s in resp.get("tombol", [])]
        return Balasan(
            teks=teks_dasar,
            tombol=tombol,
            id_respons=resp.get("id", "RSP-F1"),
            darurat=False,
        )

    # 4. Definisi istilah dari glosarium
    intent_tag = terpilih.tag if terpilih else "fallback"
    if intent_tag == "definisi_istilah" and "istilah" in entity:
        kode_ist = entity["istilah"]
        item_glos = kb.ambil_istilah(kode_ist)
        if item_glos:
            sumber_ist = item_glos.get("sumber", "BMKG & BNPB")
            teks = f"{item_glos['definisi']}\n\nDalam keadaan darurat, hubungi **112**.\n\nSumber: {sumber_ist}"
            tombol = [
                Tombol(label="Istilah Lainnya", payload="m:definisi_istilah:"),
                Tombol(label="Mitos vs Fakta", payload="m:mitos_hoaks:"),
                Tombol(label="Menu Bantuan", payload="m:menu_bantuan:"),
            ]
            return Balasan(
                teks=teks,
                tombol=tombol,
                id_respons=f"GLOS-{kode_ist.upper()[:10]}",
                darurat=False,
            )

    # 5. Jawaban standar dari responses.json
    resp = kb.ambil_respons(intent_tag, entity)
    if not resp:
        resp = kb.ambil_respons("fallback", {})
        return Balasan(
            teks=resp.get("teks", "Maaf, informasi belum tersedia."),
            tombol=[_buat_tombol_dari_spek(s) for s in resp.get("tombol", [])],
            id_respons=resp.get("id", "RSP-F1"),
            darurat=False,
        )

    tombol = [_buat_tombol_dari_spek(s) for s in resp.get("tombol", [])]
    return Balasan(
        teks=_format_teks_dengan_sumber(resp, darurat=False),
        tombol=tombol,
        id_respons=resp.get("id"),
        darurat=False,
    )

