# Laporan Evaluasi Kinerja — Exact k-NN (SIKA)

Konfigurasi uji: N=100000, D=384, Q=1000, k=10, reps=3 (median). K7 diukur pada N=500000.

## Ringkasan Kriteria Kelulusan (Tabel 4.2)

| Kode | Kriteria | Ambang | Hasil | Status |
|------|----------|--------|-------|--------|
| K1 | Speedup OpenMP 4 thread vs baseline | ≥ 2,5× | 17.23× | ✅ PASS |
| K2 | Speedup CUDA vs baseline (batch) | ≥ 20× | 244.55× | ✅ PASS |
| K3 | Latensi p95 CUDA per-query | ≤ 100 ms | 2.586 ms | ✅ PASS |
| K4 | Latensi p95 sistem POST /search | ≤ 100 ms | lihat catatan (uji N=100k: p95 11,7 ms) | ✅ PASS |
| K5 | Recall top-k tiap varian vs baseline | = 100% | 100% (identik baseline) | ✅ PASS |
| K6 | Parallel efficiency OpenMP 4 thread | ≥ 62,5% | 74.6% | ✅ PASS |
| K7 | Jejak memori per proses MPI (P=4) | ≥ 3× lebih kecil | 3.7× | ✅ PASS |

## Data Mentah (ms / QPS)

| Pengukuran | median (ms) | QPS | p95 (ms) | recall |
|------------|-------------|-----|----------|--------|
| baseline_batch | 18837.707 | 53.09 | 0.000 | 1 |
| openmp1_batch | 3262.447 | 306.52 | 0.000 | 1 |
| openmp4_batch | 1093.152 | 914.79 | 0.000 | 1 |
| baseline_single | 19.508 | 51.26 | 21.688 | 1 |
| cuda_batch | 77.029 | 12982.15 | 0.000 | 1 |
| cuda_single | 1.942 | 514.94 | 2.586 | 1 |

## MPI — Jejak Memori per Proses

| Proses (P) | Waktu komputasi (ms) | RSS/proses (KB) |
|------------|----------------------|-----------------|
| 1 | 9349.1 | 770532 |
| 4 | 3443.3 | 208020 |

Reduksi jejak memori (P=1 → P=4): **3.7×**

## Catatan Metodologi

- **Baseline** = CPU single-thread, `d2 = Σ(q−p)²` langsung (acuan).
- **OpenMP** = query-block parallelism + `#pragma omp simd` + cache tiling.
- **CUDA** = `cublasSgemm` (Q·basisᵀ) untuk shortlist + **refine eksak** `Σ(q−p)²` pada kandidat agar recall identik baseline (mengatasi catastrophic cancellation float32).
- **MPI** = sharding kontigu per rank (tiap proses memuat hanya N/P baris) + `MPI_Gather` top-k → merge eksak di rank 0.
- **K5** divalidasi dengan membandingkan himpunan indeks top-k per query vs baseline.
- **K4** diukur terpisah via `POST /bench` (300 query) pada N=100.000, engine openmp: p95 ≈ 11,7 ms.
