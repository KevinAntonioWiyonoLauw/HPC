# hpc-knn-sika

Akselerasi **Exact k-NN** untuk retrieval sistem RAG, dibungkus sebagai aplikasi
demo **SIKA** (Sistem Informasi Kepatuhan Internal). Proyek mata kuliah
Arsitektur dan Infrastruktur Berkinerja Tinggi.

Target: latensi retrieval **p95 ≤ 100 ms** pada N hingga 500.000, D = 384,
**recall 100%** (Exact, bukan ANN).

## Struktur

```
engine/   C++ core: baseline, openmp, cuda, mpi (share include/knn_engine.h)
  include/knn_engine.h   kontrak KnnSearchFn (Listing V.1)
  include/knn_util.h     timer, bounded max-heap top-k, loader, registry
  src/baseline.cpp       sekuensial + mode single-query (via bench)
  src/openmp_knn.cpp     query-block parallel + SIMD + cache tiling
  src/cuda_knn.cu        GEMM-form + shared memory + block reduction
  bench/bench_main.cpp   harness: p50/p95/p99, QPS, recall self-check
  bench/mpi_bench.cpp    shard + Gather top-k (exact), jejak memori/proses
  bindings/pybind_module.cpp  expose SikaEngine ke Python
data/     gen_synthetic.py, build_corpus, sop_synthetic/
scripts/  run_bench_matrix, evaluate_all, recall_check, build_binding, run_service
service/  FastAPI (/ask /search /engine /config /models /bench) + embed + llm
web/      Vite + React + TS (panel telemetri)
results/  raw CSV + report (kpi_summary.json)
```

## Engine (kontrak `KnnSearchFn` — Listing V.1)

| Engine   | Teknik                                        | Kriteria |
|----------|-----------------------------------------------|----------|
| baseline | CPU single-thread sekuensial                  | acuan    |
| openmp   | query-block parallel + SIMD + cache tiling    | K1, K6   |
| cuda     | GEMM + shared memory + parallel reduction     | K2, K3   |
| mpi      | sharding + Gather (exact, out-of-core)        | K7       |

## Environment

- WSL2 Ubuntu 24.04, gcc 13, cmake, OpenMPI, CUDA Toolkit (opsional)
- Python venv di `.venv` (numpy, fastapi, uvicorn, sentence-transformers, torch CPU)
- Node 22 untuk frontend
- GPU: NVIDIA GTX 1650 4 GB (compute capability 7.5)

## Build engine

```bash
cd engine
make bench bench_openmp     # baseline + openmp
make bench_cuda             # butuh nvcc + GPU
make mpi                    # butuh mpic++
```

## Jalankan service + web

```bash
# 1) bangun binding Python (baseline+openmp; tambahkan cuda bila siap)
bash scripts/build_binding.sh

# 2) bangun korpus demo (embedding MiniLM)
bash scripts/_build_corpus.sh      # -> data/embeddings/sika.f32/.json

# 3) jalankan API (auto-translate localhost -> IP host WSL untuk LLM)
bash scripts/run_service.sh        # http://127.0.0.1:8000

# 4) jalankan web (terminal lain)
cd web && npm install && npm run dev   # http://localhost:5173
```

Web mem-proxy `/api` ke backend, jadi buka `http://localhost:5173`.

## LLM provider (OpenAI-compatible)

Dikonfigurasi via `.env` (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) atau
runtime lewat tombol **⚙ Provider** di UI (Fetch Models dari `GET /v1/models`).
Bila provider gagal / rate-limit (429), service otomatis fallback ke jawaban
**extractive** dari pasal hasil retrieval, sehingga demo tetap jalan offline.

> Catatan WSL2: provider di Windows tidak bisa diakses lewat `127.0.0.1` dari WSL.
> `scripts/run_service.sh` otomatis mengganti `localhost`/`127.0.0.1` pada
> `LLM_BASE_URL` dengan IP gateway host Windows.

## Evaluasi & kriteria kelulusan (Tabel 4.2)

```bash
# rangkum K1..K7 (butuh data uji; lihat scripts/evaluate_all.py)
python scripts/evaluate_all.py --n 100000 --d 384 --q 1000 --k 10 --reps 3

# recall (K5) antar engine
python scripts/recall_check.py --from-engines --basis data/out/basis_100000_384.bin \
  --queries data/out/queries_1000_384.bin --n 100000 --d 384 --q 1000 --k 10 --compare openmp
```

| Kode | Kriteria | Ambang |
|------|----------|--------|
| K1 | Speedup OpenMP 4 thread vs baseline | ≥ 2,5× |
| K2 | Speedup CUDA vs baseline (batch) | ≥ 20× |
| K3 | Latensi p95 CUDA per-query | ≤ 100 ms |
| K4 | Latensi p95 sistem `/search` | ≤ 100 ms |
| K5 | Recall top-k tiap varian vs baseline | = 100% |
| K6 | Parallel efficiency OpenMP 4 thread | ≥ 62,5% |
| K7 | Jejak memori per proses MPI (P=4) | ≥ 3× lebih kecil |

## Konfigurasi

Salin `.env.example` → `.env` lalu isi `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
`.env` tidak di-commit (lihat `.gitignore`).

## Docker Compose (cepat)

Bungkus seluruh sistem (backend + web) dalam container:
```bash
python scripts/build_corpus.py --filler 20000   # siapkan korpus (volume)
docker compose up -d --build
# Web: http://localhost:8088   API: http://localhost:8000
```
Detail (GPU, LLM, tanpa-GPU, port) ada di `DOCKER.md`.
