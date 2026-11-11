<p align="center">
  <img src="web/static/sigap-title.svg" alt="SIGAP — Sistem Informasi Gawat Darurat dan Antisipasi Penanggulangan" width="100%" />
</p>

**SIGAP** adalah aplikasi web chatbot edukasi kesiapsiagaan bencana berbasis aturan (*rule-based*) yang berjalan penuh di komputer lokal menggunakan **Python + Flask**, **MySQL/MariaDB dari XAMPP**, dan **HTML/CSS/JavaScript** (tanpa dependensi internet atau LLM).

Seluruh panduan kebencanaan merujuk pada sumber resmi **BNPB**, **BMKG**, dan **PVMBG** untuk menjawab tiga pertanyaan inti kebencanaan (**Sebelum**, **Saat**, dan **Sesudah** bencana) pada **Gempa Bumi**, **Banjir**, dan **Tanah Longsor** (serta Tsunami, Gunung Api, Angin Kencang, Tas Siaga, Jalur Evakuasi, Kelompok Rentan, Glosarium Istilah, Mitos vs Fakta, dan Kontak Darurat **112/115**).

---

## Tampilan Antarmuka Chatbot

<p align="center">
  <img src="screenshot/Screenshot%202026-11-11%20153611.png" alt="Sapaan & Panduan Situasi Khusus Banjir di Kendaraan" width="100%" />
</p>

<p align="center">
  <img src="screenshot/Screenshot%202026-11-11%20153630.png" alt="Panduan Jalur Evakuasi & Glosarium Kebencanaan" width="49%" />
  <img src="screenshot/Screenshot%202026-11-11%20153646.png" alt="Klarifikasi Multi-Giliran & Panduan Sesudah Banjir" width="49%" />
</p>

<p align="center">
  <img src="screenshot/Screenshot%202026-11-11%20153729.png" alt="Kontak Darurat & Daftar Tas Siaga Bencana" width="49%" />
  <img src="screenshot/Screenshot%202026-11-11%20153750.png" alt="Menu Topik Bantuan & Deteksi Darurat Aktif (SOS)" width="49%" />
</p>

---

## Fitur Utama

1. **Deteksi Darurat Prioritas Tertinggi (P0):** Mendeteksi kalimat kondisi darurat aktif (*"tolong terjebak banjir"*, *"ada yang tertimbun longsor"*, *"sos"*) sebelum skoring intent biasa dan langsung menampilkan panduan penyelamatan ringkas beserta informasi kontak darurat **112 / 115**.
2. **NLU Rule-Based Deterministik & Tahan Typo:**
   - Normalisasi teks, kamus bahasa sehari-hari/slang (`kb/slang.json`), dan pencocokan batas kata.
   - Toleransi salah ketik (*fuzzy matching* `rapidfuzz` dengan ambang `0.85` untuk kata $\ge 4$ huruf, misal `gmpa` $\rightarrow$ `gempa`).
   - Rumus skoring transparan: kata kunci kuat berbobot `3`, kata kunci pendukung berbobot `1`, $\text{confidence} = \min(1.0, \text{skor mentah} / 6)$, ambang minimal `0.50`, dan deteksi ambiguitas bila selisih dua kandidat teratas `< 0.15`.
3. **Konteks Percakapan Multi-Giliran & Klarifikasi Interaktif:**
   - Menyimpan konteks bencana, fase, dan intent terakhir di Flask session (kedaluwarsa otomatis setelah 10 menit tanpa aktivitas).
   - Menanyakan klarifikasi bernomor (`01.`, `02.`, dst.) bila pengguna belum menyebutkan jenis bencana atau fase, serta mendukung balasan berupa kata kunci maupun nomor pilihan.
4. **Arsitektur Tahan-Gagal (*Fail-Safe*):**
   - **Core Engine Murni (`core/`):** Bebas dari dependensi Flask maupun database.
   - **Tahan Kegagalan MySQL:** Jika MySQL XAMPP belum dinyalakan, chatbot **tetap menjawab normal** (pencatatan log dilewati secara aman).
   - **Mode Darurat Bawaan:** Jika berkas JSON di `kb/` rusak, aplikasi tetap menyala menggunakan `core/fallback_bawaan.py` agar layanan nomor darurat **112** dan langkah keselamatan dasar tidak pernah mati.

---

## Struktur Proyek

```text
sigap-bot/
├── app.py                      # Titik masuk Flask (route handler + inisialisasi)
├── config.py                   # Pembacaan .env & konstanta NLU/Sesi/Batas
├── kb_loader.py                # Pemuat & validator Knowledge Base + fallback mode bawaan
├── core/                       # Core Engine murni (TANPA Flask / PyMySQL)
│   ├── model.py                # Dataclass: PesanMasuk, Sesi, HasilNLU, Balasan, Keputusan
│   ├── normalizer.py           # Normalisasi teks & kamus slang
│   ├── emergency.py            # Detektor darurat aktif (P0)
│   ├── entities.py             # Ekstraktor entity (bencana, fase, situasi, kelompok, istilah)
│   ├── intents.py              # Skoring confidence intent & fuzzy matching
│   ├── context.py              # Resolusi konteks multi-giliran & TTL sesi
│   ├── dialog.py               # State machine dialog (IDLE, MENUNGGU_KLARIFIKASI, MODE_DARURAT)
│   ├── responder.py            # Penyusun balasan, sumber resmi, dan daftar klarifikasi
│   ├── engine.py               # Antarmuka utama Core.proses(pesan, sesi)
│   └── fallback_bawaan.py      # KB cadangan jika berkas JSON utama gagal dimuat
├── kb/                         # Knowledge Base (JSON)
│   ├── entities.json
│   ├── intents.json
│   ├── responses.json
│   ├── glossary.json
│   ├── contacts.json
│   └── slang.json
├── web/                        # Antarmuka Web & Keamanan Tampilan
│   ├── formatter.py            # Escape HTML & konversi format aman (anti-XSS)
│   ├── templates/
│   │   └── index.html          # Halaman utama chat SIGAP (Tactical Field Manual UI)
│   └── static/
│       ├── style.css
│       ├── chat.js
│       └── sigap-title.svg
├── db/                         # Integrasi Database MySQL XAMPP
│   ├── koneksi.py              # Koneksi PyMySQL
│   ├── repository.py           # Pencatatan log, feedback, dan masking PII
│   └── schema.sql              # Skrip SQL pembuatan database & tabel (untuk phpMyAdmin)
├── tools/                      # Peralatan Validasi & Evaluasi CLI
│   ├── validate_kb.py          # Validasi skema, referensi, dan aturan keselamatan KB
│   ├── coverage_report.py      # Laporan matriks cakupan Bencana × Fase
│   ├── run_eval.py             # Evaluasi akurasi NLU terhadap bank uji
│   └── bersihkan_log.py        # Pembersih log MySQL lama
├── tests/                      # Pengujian Otomatis (pytest)
│   ├── test_normalizer.py
│   ├── test_entities.py
│   ├── test_intents.py
│   ├── test_dialog.py
│   ├── test_darurat.py
│   ├── test_percakapan.py      # Skenario multi-giliran + 13 kasus uji kritis + API
│   └── test_cases.json         # Bank uji 96 pertanyaan pengguna
├── requirements.txt
├── .env.example
└── README.md
```

---

## Panduan Menjalankan Lokal (XAMPP + Flask)

### 1. Prasyarat
- **XAMPP** terpasang (hanya modul **MySQL** yang digunakan; Apache hanya diperlukan bila ingin membuka phpMyAdmin).
- **Python 3.10+**.
- Browser modern (Chrome, Edge, Firefox).

### 2. Langkah Setup (Sekali Saja)

1. **Nyalakan MySQL di XAMPP:**
   Buka **XAMPP Control Panel** $\rightarrow$ klik **Start** pada modul **MySQL** (dan Apache bila ingin membuka phpMyAdmin).
2. **Buat Tabel Database:**
   Buka `http://localhost/phpmyadmin` $\rightarrow$ klik tab **SQL** $\rightarrow$ salin dan tempel seluruh isi berkas `db/schema.sql` $\rightarrow$ klik **Go**.
3. **Siapkan Virtual Environment & Paket Python:**
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Konfigurasi `.env`:**
   Salin `.env.example` menjadi `.env`:
   ```powershell
   copy .env.example .env
   ```
5. **Validasi Knowledge Base:**
   ```powershell
   python tools/validate_kb.py
   ```

### 3. Menjalankan Aplikasi

```powershell
python app.py
```

Buka **http://127.0.0.1:5000** di browser Anda:
- Halaman Chat Utama: `http://127.0.0.1:5000/`
- Cek Kesehatan Sistem: `http://127.0.0.1:5000/health`

---

## Menjalankan Pengujian & Evaluasi Kualitas

```powershell
# 1. Validasi aturan keselamatan & struktur Knowledge Base
python tools/validate_kb.py

# 2. Cek matriks cakupan Bencana x Fase
python tools/coverage_report.py

# 3. Evaluasi akurasi NLU pada bank uji (target >= 85%, darurat = 100%)
python tools/run_eval.py

# 4. Jalankan seluruh unit test, percakapan, & 13 kasus uji kritis
pytest -v
```

---

## Pemecahan Masalah Umum (Troubleshooting)

| Masalah | Penyebab Umum | Solusi |
|---|---|---|
| MySQL di XAMPP tidak mau start | Port `3306` dipakai layanan MySQL lain | Hentikan service MySQL lain di Windows Services, atau sesuaikan `DB_PORT` di `.env` |
| Log database tidak tercatat | Modul MySQL di XAMPP belum dinyalakan atau `schema.sql` belum dijalankan | Nyalakan MySQL di XAMPP dan jalankan `db/schema.sql` di phpMyAdmin; cek status di `/health` |
| `Access denied for user 'root'` | Password root MySQL Anda tidak kosong | Isi `DB_PASSWORD` di `.env` sesuai konfigurasi XAMPP Anda |
| Port `5000` sudah dipakai aplikasi lain | Proses lain menggunakan port 5000 | Ubah nilai `PORT=5001` di berkas `.env` lalu jalankan ulang `python app.py` |
| Tampilan CSS/JS belum berubah setelah diedit | Cache browser | Tekan `Ctrl + F5` di browser untuk muat ulang paksa |
