# Runbook Demo SIKA (D1–D7)

Panduan menjalankan demo langsung di depan penguji. Semua perintah dijalankan di
WSL (Ubuntu), dari root repo `~/.../hpc-knn-sika` (di Windows: `G:\Project\Kuliah\HPC\hpc-knn-sika`).

## Persiapan sekali di awal

```bash
# 1) Bangun engine (baseline + openmp + cuda)
cd engine && make bench bench_openmp bench_cuda && cd ..

# 2) Bangun binding Python (baseline+openmp+cuda) untuk service
bash scripts/build_binding.sh

# 3) Siapkan korpus demo (SOP terkurasi + filler ~20k potongan)
bash scripts/build_corpus.py --filler 20000   # -> data/embeddings/sika.f32/.json

# 4) Pastikan .env berisi provider LLM (lihat .env.example)
```

## Menjalankan sistem (D1)

Terminal 1 — API:
```bash
bash scripts/run_service.sh          # http://0.0.0.0:8000 (auto-translate localhost->host WSL)
```
Terminal 2 — Web:
```bash
cd web && npm install && npm run dev # http://localhost:5173
```
Buka `http://localhost:5173`. Halaman menampilkan jumlah pasal terindeks + engine aktif (D1).

## Alur demo

- **D2 — Tanya normal**: ketik pertanyaan kepatuhan nyata, mis.
  *"Apakah pembelian lisensi perangkat lunak senilai 40 juta memerlukan dua penawaran pembanding?"*
  → jawaban + kutipan pasal + panel telemetri (embedding / retrieval / LLM / total).

- **D3 — Beban serentak**: klik **Bench 100×** pada engine `baseline`.
  → tampil QPS dan p50/p95.

- **D4 — Tukar engine live**: klik `openmp` lalu `cuda` pada panel "Engine aktif"
  (tanpa restart). Ulangi **Bench 100×** → QPS & p95 baru tampil berdampingan.

- **D5 — Verifikasi recall**: bandingkan kutipan pasal untuk pertanyaan sama pada
  `baseline` vs `cuda` — himpunan pasal identik (recall 100%).

- **D6 — Keputusan pengguna**: jawab ulang pertanyaan pada engine tercepat; total
  < 1 detik (retrieval < 100 ms + LLM).

- **D7 — Ketahanan (tanpa GPU)**: bila GPU bermasalah, jalankan ulang service
  dengan engine CPU. Binding tanpa CUDA dibangun lewat `build_binding.sh` (otomatis
  melewatkan CUDA bila objek tidak ada); demo D1–D3 diulang < 1 menit.

## Konfigurasi provider LLM (runtime)

Klik **⚙ Provider** di UI:
1. Isi **Base URL** (mis. `http://localhost:12800/v1`) dan **API Key**.
2. Klik **Fetch Models** → pilih model dari daftar (mis. `cb/auto`).
3. **Simpan**.

Bila provider rate-limit/gagal, jawaban otomatis **fallback extractive** dari pasal
hasil retrieval (demo tetap jalan).

## Catatan penting

- Dari WSL, provider LLM di Windows harus diakses via IP host (bukan `127.0.0.1`);
  `run_service.sh` sudah menanganinya otomatis.
- Untuk engine CUDA, `LD_LIBRARY_PATH=/usr/lib/wsl/lib` harus dipakai agar
  `libcuda.so` WSL terpilih (sudah diset di `run_service.sh`).
- Ukur performa retrieval murni dengan `POST /search` (tanpa latensi LLM).
