"""Normalisasi teks masukan pengguna: huruf kecil, tanda baca, karakter kontrol, dan slang."""

import re
from typing import Dict

# Karakter kontrol ASCII (kecuali spasi biasa)
_RE_KONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")

# Pertahankan huruf, angka, spasi, dan tanda hubung di tengah kata ulang (mis. jaga-jaga)
_RE_TANDA_BACA = re.compile(r"[^\w\s\-]|_", re.UNICODE)
_RE_HUBUNG_LEPAS = re.compile(r"(?<!\w)-|-(?!\w)")

# Huruf berulang >= 3 kali berturut-turut (mis. "gempaaa" -> "gempa", "tolooong" -> "tolong")
_RE_HURUF_BERULANG = re.compile(r"([a-zA-Z])\1{2,}")

# Spasi berlebih
_RE_SPASI = re.compile(r"\s+")


def bersihkan_karakter_kontrol(teks: str) -> str:
    """Menghapus karakter kontrol berbahaya dari teks."""
    if not isinstance(teks, str):
        return ""
    return _RE_KONTROL.sub(" ", teks)


def normalisasi(teks: str, kamus_slang: Dict[str, str] | None = None) -> str:
    """Menormalisasi teks pengguna menjadi teks bersih siap diproses NLU.

    Tahapan:
    1. Buang karakter kontrol dan ubah ke huruf kecil (lowercase).
    2. Sederhanakan huruf berulang >= 3 (contoh: 'gempaaa' -> 'gempa').
    3. Buang tanda baca selain tanda hubung di tengah kata ulang.
    4. Ganti singkatan/slang berdasarkan kamus_slang per kata.
    5. Rapikan spasi berlebih.
    """
    if not isinstance(teks, str):
        return ""

    teks = bersihkan_karakter_kontrol(teks).lower()
    teks = _RE_HURUF_BERULANG.sub(r"\1", teks)
    teks = _RE_TANDA_BACA.sub(" ", teks)
    teks = _RE_HUBUNG_LEPAS.sub(" ", teks)
    teks = _RE_SPASI.sub(" ", teks).strip()

    if not teks:
        return ""

    slang = kamus_slang or {}
    kata_hasil = []
    for kata in teks.split(" "):
        if kata in slang:
            kata_hasil.append(slang[kata])
        elif "-" in kata:
            # Cek apakah kata ulang atau bagiannya ada di kamus slang
            bagian = [slang.get(b, b) for b in kata.split("-")]
            kata_ulang = "-".join(bagian)
            kata_hasil.append(slang.get(kata_ulang, kata_ulang))
        else:
            kata_hasil.append(kata)

    return _RE_SPASI.sub(" ", " ".join(kata_hasil)).strip()

