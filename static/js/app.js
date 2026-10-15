/* ==========================================================
   01. MENUNGGU HALAMAN SIAP
   Interaksi dijalankan setelah elemen HTML selesai dimuat oleh browser.
   ========================================================== */
document.addEventListener("DOMContentLoaded", () => {
  /* ==========================================================
     02. TAMPILAN HEADER SAAT SCROLL
     Mengubah gaya header ketika halaman digulir lebih dari 16 piksel.
     ========================================================== */
  const header = document.querySelector("[data-site-header]");
  const updateHeader = () => header?.classList.toggle("is-scrolled", window.scrollY > 16);
  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  /* ==========================================================
     03. NAVIGASI PADA LAYAR KECIL
     Menutup menu Bootstrap setelah tautan dipilih pada layar di bawah 992 piksel.
     ========================================================== */
  const navigation = document.getElementById("mainNavigation");
  if (navigation && window.bootstrap) {
    navigation.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (window.innerWidth < 992 && navigation.classList.contains("show")) {
          bootstrap.Collapse.getOrCreateInstance(navigation).hide();
        }
      });
    });
  }

  /* ==========================================================
     04. ANIMASI KEMUNCULAN KONTEN
     Menampilkan bagian saat masuk layar sambil menghormati preferensi pengurangan animasi.
     ========================================================== */
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const revealTargets = document.querySelectorAll(
    "main > section, main > .page-header, .catalog-section, .dashboard-content > *",
  );
  if (!reduceMotion && "IntersectionObserver" in window && revealTargets.length) {
    document.body.classList.add("reveal-ready");
    revealTargets.forEach((target) => target.classList.add("reveal-section"));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -35px" },
    );
    revealTargets.forEach((target) => observer.observe(target));
  }

  /* ==========================================================
     05. PESAN HASIL PROSES
     Membaca pesan Flask dari HTML dan menampilkannya sebagai toast SweetAlert.
     ========================================================== */
  const flashContainer = document.getElementById("flash-messages");
  if (flashContainer && window.Swal) {
    const messages = JSON.parse(flashContainer.dataset.messages);
    messages.forEach(([category, message]) =>
      Swal.fire({
        toast: true,
        position: "top-end",
        icon: category === "danger" ? "error" : category,
        title: message,
        showConfirmButton: false,
        timer: 3500,
      }),
    );
  }

  /* ==========================================================
     06. PILIHAN TANGGAL
     Memasang kalender pada input datepicker dengan tanggal paling awal hari ini.
     ========================================================== */
  if (window.flatpickr) {
    flatpickr(".datepicker", { dateFormat: "Y-m-d", minDate: "today" });
  }

  /* ==========================================================
     07. KONFIRMASI FORMULIR
     Meminta konfirmasi untuk form bertanda data-confirm sebelum dikirim.
     ========================================================== */
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.confirmed) return;
      event.preventDefault();
      if (!window.Swal) {
        if (window.confirm(form.dataset.confirm)) {
          form.dataset.confirmed = "1";
          form.submit();
        }
        return;
      }
      Swal.fire({
        title: form.dataset.confirm,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Ya, lanjutkan",
        cancelButtonText: "Batal",
      }).then((result) => {
        if (result.isConfirmed) {
          form.dataset.confirmed = "1";
          form.submit();
        }
      });
    });
  });

  /* ==========================================================
     08. PRATINJAU GAMBAR UNGGAHAN
     Menampilkan gambar yang dipilih dan melepas URL pratinjau sebelumnya.
     ========================================================== */
  document.querySelectorAll(".image-preview-input").forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.files[0]) return;
      const previous = input.parentElement.querySelector(".image-preview");
      if (previous?.dataset.objectUrl) URL.revokeObjectURL(previous.dataset.objectUrl);
      previous?.remove();
      const objectUrl = URL.createObjectURL(input.files[0]);
      const image = document.createElement("img");
      image.src = objectUrl;
      image.alt = "Pratinjau gambar yang dipilih";
      image.dataset.objectUrl = objectUrl;
      image.className = "image-preview img-thumbnail mt-2";
      image.style.maxHeight = "140px";
      input.parentElement.appendChild(image);
    });
  });
});
