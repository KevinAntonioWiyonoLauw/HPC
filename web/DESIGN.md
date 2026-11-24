# DESIGN.md — Identitas Visual SIKA

Dokumen ini adalah sumber kebenaran palet dan karakter visual SIKA. Semua warna,
radius, dan tipografi diturunkan dari sini, bukan dari default model.

## Karakter produk

SIKA (Sistem Informasi Kepatuhan Internal) adalah konsol pencarian dokumen
kepatuhan untuk staf unit kepatuhan. Pekerjaan utamanya satu: **ajukan pertanyaan
kepatuhan, dapatkan jawaban yang dikutip ke pasal asli**, dan bila perlu
**bandingkan kecepatan engine** serta **kelola berkas regulasi**. Nada: institusional,
tenang, presisi, dapat dipercaya. Bukan produk AI yang ramai.

## Palet (2 inti + 1 aksen)

- **Kertas (netral hangat)** — latar terang, bukan putih steril.
  - background `hsl(40 33% 97%)`, card `hsl(0 0% 100%)`, muted `hsl(40 20% 93%)`.
- **Tinta (netral gelap)** — teks dan permukaan gelap.
  - foreground `hsl(200 24% 13%)`, border `hsl(40 12% 86%)`.
- **Aksen tunggal: verdigris (teal institusional)** — dipakai hemat, hanya untuk
  aksi utama, item nav aktif, dan satu penekanan per layar.
  - light `hsl(174 62% 26%)`, dark `hsl(174 52% 46%)`.

Warna status: sukses hijau `hsl(152 55% 30%)`, peringatan amber `hsl(32 80% 40%)`,
bahaya merah `hsl(0 62% 46%)`. Status hanya dipakai untuk makna (lulus/gagal/antre),
tidak sebagai hiasan.

Alasan: aksen tunggal menjaga satu titik fokus; netral hangat memberi kesan dokumen
resmi, bukan kanvas AI. Gradient biru-ungu, glow, dan orb blur **dilarang**.

## Tipografi

- Judul/brand: **serif editorial** (Iowan Old Style / Palatino / Georgia) untuk
  kesan dokumen resmi. Hanya untuk wordmark dan judul halaman.
- UI/body: **sans sistem** (system-ui, Segoe UI, Roboto). Tidak memuat font
  default tren (Inter/Geist/Space Grotesk) sebagai "identitas".
- Angka metrik: `font-variant-numeric: tabular-nums` agar kolom angka rata.

## Radius, bayangan, gerak

- Radius kecil dan konsisten: `--radius 0.5rem`; sm 0.25, md 0.375, lg 0.5.
  Tidak semua elemen pill.
- Bayangan hanya untuk elevasi nyata (menu/dialog), bukan semua kartu.
- Gerak: transisi hover/fokus halus saja (MOTION dial = 1). Tidak ada pulse/loop
  tanpa henti. Hormati `prefers-reduced-motion`.

## Aturan tata letak

- Shell aplikasi: sidebar navigasi kiri (Tanya, Benchmark, Dokumen, Pengaturan,
  Ikhtisar) + area kerja. Sidebar menandai halaman aktif dengan aksen, tanpa dot
  dekoratif.
- Setiap layar dibangun dari pekerjaannya: layar Tanya berpusat pada kotak tanya
  dan jawaban berkutipan; layar Dokumen berpusat pada daftar berkas dan unggah;
  layar Benchmark pada tabel/grafik perbandingan engine.
- Data nyata saja. Angka/daftar berasal dari API; bila kosong tampilkan empty state
  yang menjelaskan sebab dan langkah berikutnya, bukan angka palsu.

## Kontras (WCAG AA)

Teks utama ≥ 7:1 pada latar; teks sekunder ≥ 4.5:1; tombol aksen putih-di-verdigris
≥ 4.5:1. Fokus keyboard selalu terlihat (ring aksen).
