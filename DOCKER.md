# Menjalankan SIKA dengan Docker Compose

Dua layanan:
- **backend** — FastAPI + engine k-NN (baseline/openmp/**cuda**) via pybind11,
  image `nvidia/cuda` multi-stage (butuh GPU NVIDIA + driver; fallback CPU tetap jalan).
- **web** — React (hasil build Vite) disajikan nginx, mem-proxy `/api` ke backend.

## Prasyarat
- Docker Desktop (WSL2 backend) dengan dukungan GPU NVIDIA
  (runtime `nvidia` terdeteksi pada `docker info`).
- Korpus SIKA sudah dibangun (dipasang sebagai volume read-only):
  ```bash
  python scripts/build_corpus.py --filler 20000   # -> data/embeddings/sika.f32/.json
  ```

## Build & jalankan
```bash
docker compose build          # sekali; backend berat (base CUDA + torch)
docker compose up -d          # web menunggu backend sehat (healthcheck)
bash scripts/verify_stack.sh  # cek /health /status /search /ask
```

Akses:
- Web  → http://localhost:8088
- API  → http://localhost:8000  (`/status`, `/search`, `/ask`, `/bench`, ...)

## Tanpa GPU (varian CPU)
Backend memiliki `healthcheck` pada `GET /health`, dan `web` menunggu
`backend` berstatus sehat sebelum start. Untuk menjalankan tanpa GPU:
```bash
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
```
Override `docker-compose.cpu.yml` mengosongkan daftar device GPU, sehingga engine
`cuda` otomatis tidak tersedia dan hanya `baseline` + `openmp` yang jalan (demo D7).

## Konfigurasi LLM
Provider OpenAI-compatible diatur lewat env (lihat `docker-compose.yml`).
Di dalam container, host Windows/WSL diakses via `host.docker.internal`:
```yaml
environment:
  - LLM_BASE_URL=http://host.docker.internal:12800/v1
  - LLM_API_KEY=...
  - LLM_MODEL=cb/auto
```
Bisa juga diubah saat runtime lewat tombol **⚙ Provider** di web.
Bila provider gagal/rate-limit, jawaban otomatis fallback *extractive*.

## Mode muat basis & konkurensi
Dua env mengatur pemakaian memori dan stabilitas latensi:

- `SIKA_LOAD_MODE` — `preload` (default, baca seluruh matriks ke RAM) atau `mmap`
  (petakan berkas `.f32` langsung dari disk, halaman dimuat sesuai kebutuhan).
  Mode `mmap` menurunkan memori proses untuk korpus besar (N=500.000) dan hasil
  pencarian identik dengan `preload`. Mode `mmap` membutuhkan korpus `.f32/.json`.
- `SIKA_MAX_CONCURRENCY` — batas jumlah pencarian engine serentak (default `1`,
  serial per device; `0` = tanpa batas). Menstabilkan p95/p99 pada beban serentak.
- `SIKA_MAX_EMBED_CONCURRENCY` — batas embedding serentak (default `4`).
- `SIKA_WARMUP` — `full` (default: embedding + engine), `engine` (lewati warmup
  embedding), atau `none` (lewati semua). `none` mempercepat start (~8,6 s vs
  ~45 s) dengan model embedding dimuat lazy saat permintaan pertama.
- `SIKA_QBLK` — ukuran blok query engine OpenMP (default `128`, dari sapuan
  `scripts/bench_qblk.sh`).

Contoh menjalankan dengan mmap:
```bash
SIKA_LOAD_MODE=mmap docker compose up -d
```
Metrik antrean (panjang antrean, waktu tunggu rata-rata) tersedia di
`GET /queue/stats`; mode muat aktif tampil di `GET /status` (`load_mode`).

## Perintah berguna
```bash
docker compose ps                 # status
docker compose logs -f backend    # log backend
docker compose exec backend nvidia-smi      # cek GPU di dalam container
bash scripts/verify_stack.sh      # verifikasi endpoint setelah up
docker compose down               # hentikan
docker compose up -d --build      # rebuild setelah ubah kode
```

## Catatan
- **Tanpa GPU**: pakai `docker-compose.cpu.yml` (lihat di atas); engine `cuda`
  otomatis tidak tersedia, `baseline`/`openmp` tetap jalan (demo D7).
- **Port**: backend `8000`, web `8088` (ubah di `docker-compose.yml` bila bentrok;
  mis. jika `8088` terpakai, ganti ke port lain).
- **Data**: `./data` dipasang read-only ke `/app/data`. Matriks `data/out` (uji
  skala besar) tidak ikut ter-build ke image.
- Model embedding (all-MiniLM-L6-v2) sudah di-*bake* ke image, jadi runtime tidak
  butuh internet.
