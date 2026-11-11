/**
 * SIGAP Frontend Chat Controller — Tactical Field Manual Civic-Tech UI
 * Prinsip Keamanan Bagian 9.6:
 * - Pesan pengguna WAJIB dirender memakai textContent (bukan innerHTML).
 * - HTML balasan bot sudah di-escape di sisi server oleh web/formatter.py.
 */

(function () {
  "use strict";

  const chatContainer = document.getElementById("chatContainer");
  const chatForm = document.getElementById("chatForm");
  const pesanInput = document.getElementById("pesanInput");
  const btnKirim = document.getElementById("btnKirim");
  const btnReset = document.getElementById("btnReset");
  const typingIndicator = document.getElementById("typingIndicator");
  const charCount = document.getElementById("charCount");

  let sedangMemproses = false;

  function waktuSekarangStr() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    return `${hh}.${mm}`;
  }

  function gulirKeBawah() {
    requestAnimationFrame(() => {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    });
  }

  function setStatusInput(nonaktif) {
    sedangMemproses = nonaktif;
    pesanInput.disabled = nonaktif;
    btnKirim.disabled = nonaktif;
    if (nonaktif) {
      typingIndicator.classList.remove("hidden");
    } else {
      typingIndicator.classList.add("hidden");
      pesanInput.focus();
    }
    gulirKeBawah();
  }

  /**
   * Menampilkan pesan pengguna secara aman menggunakan textContent (Anti-XSS Bagian 9.6)
   */
  function tambahPesanPengguna(teks) {
    const article = document.createElement("article");
    article.className = "msg-block-user";

    const header = document.createElement("header");
    header.className = "msg-header-user";

    const sender = document.createElement("span");
    sender.className = "msg-sender-user";
    sender.textContent = "KAMU";

    const dot = document.createElement("span");
    dot.className = "msg-dot";
    dot.textContent = "•";

    const timeEl = document.createElement("time");
    timeEl.className = "msg-time";
    timeEl.textContent = waktuSekarangStr();

    header.appendChild(sender);
    header.appendChild(dot);
    header.appendChild(timeEl);

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble-user";
    bubble.textContent = teks; // WAJIB textContent, jangan pernah innerHTML!

    article.appendChild(header);
    article.appendChild(bubble);
    chatContainer.appendChild(article);
    gulirKeBawah();
  }

  /**
   * Menampilkan blok pesan bot bergaya Tactical Field Manual
   * - tone-navy (#0F172A) untuk sapaan pembuka (RSP-U1)
   * - tone-amber (#D97706) untuk protokol dan arahan kesiapsiagaan
   * - tone-vermilion (#DC2626) untuk kondisi darurat aktif
   */
  function tambahPesanBot(dataRespons, adalahSapaan = false) {
    const balasan = dataRespons.balasan || {};
    const isDarurat = Boolean(balasan.darurat);
    const idRespons = dataRespons.id_respons || "";

    let kelasNada = "tone-amber";
    if (isDarurat) {
      kelasNada = "tone-vermilion";
    } else if (adalahSapaan || idRespons === "RSP-U1" || idRespons === "RSP-U2" || idRespons === "RSP-U3") {
      kelasNada = "tone-navy";
    }

    const article = document.createElement("article");
    article.className = `msg-block-bot ${kelasNada}`;

    const header = document.createElement("header");
    header.className = "msg-header-bot";

    const sender = document.createElement("span");
    sender.className = "msg-sender-bot";
    sender.textContent = isDarurat ? "SIGAP — DARURAT" : "SIGAP";

    const dot = document.createElement("span");
    dot.className = "msg-dot";
    dot.textContent = "•";

    const timeEl = document.createElement("time");
    timeEl.className = "msg-time";
    timeEl.textContent = waktuSekarangStr();

    header.appendChild(sender);
    header.appendChild(dot);
    header.appendChild(timeEl);

    const bodyDiv = document.createElement("div");
    bodyDiv.className = "msg-body-bot";
    bodyDiv.innerHTML = balasan.html || '<p class="msg-paragraph">Maaf, respons kosong.</p>';

    article.appendChild(header);
    article.appendChild(bodyDiv);

    // Jika respons darurat tidak memiliki footer sumber, tambahkan catatan sumber resmi
    if (isDarurat && !bodyDiv.querySelector(".msg-citation")) {
      const footer = document.createElement("footer");
      footer.className = "msg-citation";
      const span = document.createElement("span");
      span.className = "msg-source";
      span.textContent = "SUMBER RESMI: BNPB, BASARNAS (112 / 115)";
      footer.appendChild(span);
      article.appendChild(footer);
    }

    chatContainer.appendChild(article);
    gulirKeBawah();
  }

  async function kirimPesan(teksTampil) {
    const teksBersih = (teksTampil || "").trim();
    if (!teksBersih || sedangMemproses) return;

    tambahPesanPengguna(teksBersih);
    pesanInput.value = "";
    charCount.textContent = "0/1000";

    setStatusInput(true);

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pesan: teksBersih,
          tombol: null,
        }),
      });

      const data = await resp.json();

      if (!resp.ok && data.error) {
        tambahPesanBot({
          balasan: {
            html: `<p class="msg-paragraph"><strong>PERINGATAN:</strong> ${data.error}</p>`,
            darurat: false,
          },
        });
      } else {
        tambahPesanBot(data, false);
      }
    } catch (_) {
      tambahPesanBot({
        balasan: {
          html:
            '<p class="msg-paragraph">Tidak dapat terhubung ke server lokal. Pastikan <code>python app.py</code> sedang berjalan. Dalam keadaan darurat, segera hubungi <strong>112</strong>.</p>',
          darurat: true,
        },
      });
    } finally {
      setStatusInput(false);
    }
  }

  async function muatSalamPembuka() {
    try {
      const resp = await fetch("/api/mulai");
      const data = await resp.json();
      tambahPesanBot(data, true);
    } catch (_) {
      tambahPesanBot(
        {
          balasan: {
            html:
              '<p class="msg-paragraph">Halo, saya SIGAP, asisten kesiapsiagaan bencana. Silakan ketik pertanyaan Anda di kolom bawah. Dalam keadaan darurat, segera hubungi 112.</p>',
            darurat: false,
          },
          id_respons: "RSP-U1",
        },
        true
      );
    }
  }

  // Event Listeners
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    kirimPesan(pesanInput.value);
  });

  pesanInput.addEventListener("input", () => {
    charCount.textContent = `${pesanInput.value.length}/1000`;
  });

  if (btnReset) {
    btnReset.addEventListener("click", async () => {
      if (sedangMemproses) return;
      setStatusInput(true);
      try {
        const resp = await fetch("/api/reset", { method: "POST" });
        const data = await resp.json();
        chatContainer.innerHTML = "";
        tambahPesanBot(data, true);
      } catch (_) {
        chatContainer.innerHTML = "";
        await muatSalamPembuka();
      } finally {
        setStatusInput(false);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    muatSalamPembuka();
    pesanInput.focus();
  });
})();
