#!/usr/bin/env bash
# profiling.sh - profiling perangkat keras untuk bukti bottleneck (Bab III & IV).
#
# Menjalankan jalur profiling bila tersedia, dan jatuh ke jalur cadangan yang
# dapat diulang. Semua hasil ditulis ke results/profiling/.
#
# Jalur yang dicoba:
#   1. CPU perf    : L1/LLC cache miss, stalls, IPC (bila PMU tersedia)
#   2. CPU cachegrind : valgrind --tool=cachegrind (bila valgrind ada)
#   3. GPU ncu     : Nsight Compute memory/compute throughput (bila izin ada)
#   4. Fallback    : roofline efektif dari waktu nyata (bandwidth & GFLOPS) +
#                    rasio komunikasi/komputasi MPI (dari mpi_bench)
#
# Pemakaian:
#   bash scripts/profiling.sh [N] [D] [Q]
# Default N=100000 D=384 Q=1000 (dataset kecil agar cepat & konsisten).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
N=${1:-100000}; D=${2:-384}; Q=${3:-1000}; K=10
OUT="$ROOT/results/profiling"; mkdir -p "$OUT"
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
BASIS="data/out/basis_${N}_${D}.bin"; QUERIES="data/out/queries_${Q}_${D}.bin"
if [ ! -f "$BASIS" ]; then
  python3 data/gen_synthetic.py --n "$N" --d "$D" --q "$Q" --outdir data/out || exit 1
fi

echo "== Konfigurasi: N=$N D=$D Q=$Q k=$K =="

# ---- 1. CPU perf (PMU) ----
if command -v perf >/dev/null 2>&1; then
  echo "[CPU] perf stat (baseline single-query)"
  OMP_NUM_THREADS=1 perf stat -e cycles,instructions,cache-misses,LLC-load-misses,stalled-cycles-frontend,stalled-cycles-backend \
    ./engine/build/bench_openmp --basis "$BASIS" --queries "$QUERIES" --n "$N" --d "$D" --q "$Q" --k "$K" \
    --engine baseline --mode batch --reps 1 > "$OUT/perf_baseline.txt" 2>&1
  echo "  -> $OUT/perf_baseline.txt"
else
  echo "[CPU] perf TIDAK tersedia (PMU tidak diekspos). Lihat fallback roofline."
fi

# ---- 2. CPU cachegrind ----
if command -v valgrind >/dev/null 2>&1; then
  echo "[CPU] cachegrind (openmp 1 thread)"
  OMP_NUM_THREADS=1 valgrind --tool=cachegrind --cachegrind-out-file="$OUT/cachegrind_openmp.out" \
    ./engine/build/bench_openmp --basis "$BASIS" --queries "$QUERIES" --n "$N" --d "$D" --q "$Q" --k "$K" \
    --engine openmp --mode batch --reps 1 > "$OUT/cachegrind_openmp.txt" 2>&1
  echo "  -> $OUT/cachegrind_openmp.txt"
else
  echo "[CPU] valgrind/cachegrind TIDAK tersedia."
fi

# ---- 3. GPU Nsight Compute ----
if command -v ncu >/dev/null 2>&1; then
  echo "[GPU] ncu metrics"
  ncu --clock-control none --target-processes all \
    --metrics gpu__time_duration.sum,sm__throughput.avg.pct_of_peak_sustained_elapsed,gpu__compute_memory_throughput.avg.pct_of_peak_sustained_elapsed,launch__occupancy_limit_active_warps \
    ./engine/build/bench_cuda --basis "$BASIS" --queries "$QUERIES" --n "$N" --d "$D" --q "$Q" --k "$K" \
    --engine cuda --mode batch --reps 1 > "$OUT/ncu_cuda.txt" 2>&1 || true
  if grep -q ERR_NVGPUCTRPERM "$OUT/ncu_cuda.txt" 2>/dev/null; then
    echo "  ncu tanpa izin (ERR_NVGPUCTPERM). Lihat fallback roofline untuk GPU."
  else
    echo "  -> $OUT/ncu_cuda.txt"
  fi
else
  echo "[GPU] ncu TIDAK tersedia."
fi

# ---- 4. Fallback roofline + MPI comm ratio ----
echo "[Fallback] roofline efektif + MPI comm ratio -> $OUT/roofline.txt"
python3 scripts/profile_roofline.py --basis "$BASIS" --queries "$QUERIES" \
  --n "$N" --d "$D" --q "$Q" --k "$K" --out "$OUT/roofline.txt"

echo "Selesai. Hasil di $OUT"
