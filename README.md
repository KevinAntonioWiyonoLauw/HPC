# hpc-knn-sika

Akselerasi **Exact k-NN** untuk retrieval sistem RAG, dibungkus sebagai aplikasi
demo **SIKA** (Sistem Informasi Kepatuhan Internal). Proyek mata kuliah
Arsitektur dan Infrastruktur Berkinerja Tinggi.

Target: latensi retrieval **p95 ≤ 100 ms** pada N hingga 500.000, D = 384.

## Struktur

```
engine/   C++ core: baseline, openmp, cuda, mpi (share include/knn_engine.h)
data/     generator data sintetis + korpus
scripts/  benchmark, recall check, profiling
service/  FastAPI (/ask /search /engine) + embedding + LLM provider
web/      Vite + React + TS (panel telemetri)
results/  raw CSV + laporan
```

## Engine (kontrak `KnnSearchFn` — Listing V.1)

| Engine   | Teknik                                        | Kriteria |
|----------|-----------------------------------------------|----------|
| baseline | CPU single-thread sekuensial                  | acuan    |
| openmp   | query-parallel + SIMD + loop tiling           | K1, K6   |
| cuda     | GEMM + shared memory + parallel reduction     | K2, K3   |
| mpi      | sharding + Bcast + Gather (opsional)          | K7       |

## Build & jalankan baseline (Fase 1)

```bash
# di WSL, dari folder engine/
make bench
./build/bench_baseline --list

# generate data uji
python data/gen_synthetic.py --n 5000 --d 384 --q 100 --outdir data/out

# benchmark
./build/bench_baseline --basis data/out/basis_5000_384.bin \
  --queries data/out/queries_100_384.bin --n 5000 --d 384 --q 100 \
  --k 10 --engine baseline --mode single-query --reps 1
```

## Konfigurasi

Salin `.env.example` → `.env` lalu isi `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
`.env` tidak di-commit (lihat `.gitignore`).
