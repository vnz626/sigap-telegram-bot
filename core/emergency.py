"""Detektor kondisi darurat aktif (Prioritas P0 — dijalankan sebelum skoring intent)."""

import re

# Frasa pemicu darurat mutlak
_FRASA_DARURAT_MUTLAK = [
    "tertimbun",
    "ada korban",
    "korban luka",
    "sekarang juga",
    "sos",
    "butuh bantuan segera",
    "butuh pertolongan segera",
    "air udah naik sepinggang",
    "air naik sepinggang",
    "air udah sedada",
    "air udah seleher",
    "keluargaku nggak ketemu",
    "keluarga nggak ketemu",
    "keluarga hilang",
    "lagi gempa sekarang",
    "lagi banjir sekarang",
    "lagi longsor sekarang",
    "sedang terjebak",
    "aku terjebak",
    "kami terjebak",
    "saya terjebak",
    "terjebak banjir",
    "terjebak longsor",
    "terjebak reruntuhan",
]

# Pertanyaan informasi/situasi yang mengandung kata "tolong" atau "terjebak"
# namun BUKAN kondisi darurat aktif (mis. "minta tolong ke mana", "terjebak di lift pas gempa")
_PENGECUALIAN_NON_DARURAT = [
    "minta tolong ke mana",
    "minta tolong ke siapa",
    "minta tolong kemana",
    "terjebak di lift pas gempa",
    "kalau terjebak",
    "gimana kalau terjebak",
    "bagaimana kalau terjebak",
    "saat terjebak di lift",
]


def _ada_batas_kata(frasa: str, teks: str) -> bool:
    pola = r"(?<!\w)" + re.escape(frasa) + r"(?!\w)"
    return bool(re.search(pola, teks))


def deteksi_darurat(teks_bersih: str) -> bool:
    """Mengembalikan True jika pesan mengindikasikan kondisi darurat aktif (P0)."""
    if not teks_bersih:
        return False

    # 1. Cek frasa darurat mutlak yang tidak tergantikan
    for frasa in _FRASA_DARURAT_MUTLAK:
        if _ada_batas_kata(frasa, teks_bersih):
            return True

    # 2. Jika memuat kata "tolong", pastikan bukan pertanyaan "minta tolong ke mana/siapa"
    if _ada_batas_kata("tolong", teks_bersih):
        for kec in _PENGECUALIAN_NON_DARURAT:
            if _ada_batas_kata(kec, teks_bersih):
                return False
        return True

    # 3. Jika memuat kata "terjebak", pastikan bukan pertanyaan situasi khusus "terjebak di lift pas gempa"
    if _ada_batas_kata("terjebak", teks_bersih):
        for kec in _PENGECUALIAN_NON_DARURAT:
            if _ada_batas_kata(kec, teks_bersih):
                return False
        return True

    return False

