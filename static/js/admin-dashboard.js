/* ==========================================================
   01. GRAFIK STATUS ARMADA
   Membaca jumlah kendaraan dari atribut HTML dan menampilkannya sebagai diagram donat Chart.js.
   ========================================================== */

/* Grafik dashboard: baca statistik dari HTML yang telah dirender Flask. */
(() => {
  const canvas = document.getElementById("statusChart");
  if (!canvas || !window.Chart) return;

  /* ==========================================================
     02. MEMBACA STATISTIK ARMADA
     Mengubah atribut jumlah kendaraan dari HTML menjadi nilai numerik untuk grafik.
     ========================================================== */
  const counts = [
    Number(canvas.dataset.available),
    Number(canvas.dataset.rented),
    Number(canvas.dataset.maintenance),
  ];

  /* ==========================================================
     03. MEMBENTUK DIAGRAM DONAT
     Mengatur label, warna tiap status, ukuran lubang, dan legenda di bawah grafik.
     ========================================================== */
  new window.Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["Tersedia", "Disewa", "Perawatan"],
      datasets: [{
        data: counts,
        backgroundColor: ["#20b77a", "#1268d6", "#ff8a00"],
        borderWidth: 0,
      }],
    },
    options: {
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            usePointStyle: true,
            padding: 18,
          },
        },
      },
    },
  });
})();
