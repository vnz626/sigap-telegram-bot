"""Formatter teks respons Knowledge Base ke HTML yang dijamin aman dari XSS (Bagian 9.6)
dengan gaya tipografi Tactical Field Manual (01., 02., dan SUMBER RESMI).
"""

import html
import re
from typing import List

_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_RE_CODE = re.compile(r"`([^`\n]+?)`")
_RE_ITEM_BERNOMOR = re.compile(r"^\s*(\d+)\.\s+(.+)$")


def _format_inline_aman(teks_escaped: str) -> str:
    """Mengubah pola inline (**tebal**, *miring*, `kode`) setelah teks di-escape."""
    hasil = _RE_BOLD.sub(r"<strong>\1</strong>", teks_escaped)
    hasil = _RE_ITALIC.sub(r"<em>\1</em>", hasil)
    hasil = _RE_CODE.sub(r"<code>\1</code>", hasil)
    return hasil


def ke_html(teks: str) -> str:
    """Mengubah teks respons KB menjadi string HTML aman dengan struktur Field Manual.

    Tahapan wajib sesuai Bagian 9.6:
    1. html.escape(teks) terlebih dahulu agar tag seperti <script> atau <b> menjadi entitas aman.
    2. Ubah pola aman (**tebal** -> <strong>, daftar "1. " -> <ol class="protocol-list"><li>01. ...</li></ol>).
    3. Kembalikan string HTML yang sudah aman.
    """
    if not isinstance(teks, str) or not teks.strip():
        return "<p></p>"

    # Langkah 1: Escape seluruh karakter berbahaya (<, >, &, ", ')
    aman = html.escape(teks.strip(), quote=True)

    baris_list = aman.splitlines()
    blok_html: List[str] = []
    buffer_ol: List[str] = []
    buffer_p: List[str] = []

    def tutup_ol() -> None:
        if buffer_ol:
            items = []
            for idx, item in enumerate(buffer_ol, start=1):
                nomor_dua_digit = f"{idx:02d}."
                items.append(
                    f'<li class="protocol-item">'
                    f'<span class="protocol-num">{nomor_dua_digit}</span>'
                    f'<div class="protocol-text">{item}</div>'
                    f'</li>'
                )
            blok_html.append(f'<ol class="protocol-list">{"".join(items)}</ol>')
            buffer_ol.clear()

    def tutup_p() -> None:
        if buffer_p:
            isi = "<br>".join(buffer_p)
            if isi.startswith("Sumber:"):
                label_sumber = isi.replace("Sumber:", "SUMBER RESMI:", 1).upper()
                blok_html.append(
                    f'<footer class="msg-citation">'
                    f'<span class="msg-source">{label_sumber}</span>'
                    f'</footer>'
                )
            else:
                blok_html.append(f'<p class="msg-paragraph">{isi}</p>')
            buffer_p.clear()

    for baris in baris_list:
        baris_rapi = baris.strip()
        if not baris_rapi:
            tutup_ol()
            tutup_p()
            continue

        cocok_ol = _RE_ITEM_BERNOMOR.match(baris_rapi)
        if cocok_ol:
            tutup_p()
            buffer_ol.append(_format_inline_aman(cocok_ol.group(2)))
        else:
            tutup_ol()
            buffer_p.append(_format_inline_aman(baris_rapi))

    tutup_ol()
    tutup_p()

    return "".join(blok_html) if blok_html else f'<p class="msg-paragraph">{_format_inline_aman(aman)}</p>'
