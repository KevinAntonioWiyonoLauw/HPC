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
