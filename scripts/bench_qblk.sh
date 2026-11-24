#!/usr/bin/env bash
# bench_qblk.sh - sapuan ukuran blok QBLK untuk engine OpenMP.
#
# Menjalankan bench_openmp untuk beberapa nilai SIKA_QBLK pada dataset yang sama,
# mencatat waktu, QPS, dan recall_ok (harus 1 = identik baseline) tiap ukuran blok.
#
# Pemakaian:
#   bash scripts/bench_qblk.sh <basis.bin> <queries.bin> <n> <d> <q> [k]
# Contoh:
#   bash scripts/bench_qblk.sh data/out/basis_100000_384.bin data/out/queries_1000_384.bin 100000 384 1000 10
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASIS=${1:?butuh basis.bin}
QUERIES=${2:?butuh queries.bin}
N=${3:?butuh n}
D=${4:?butuh d}
Q=${5:?butuh q}
K=${6:-10}

BIN="engine/build/bench_openmp"
if [ ! -x "$BIN" ]; then
  echo "bench_openmp belum dibangun; jalankan: make -C engine bench_openmp" >&2
  exit 1
fi

echo "Sapuan QBLK: N=$N D=$D Q=$Q k=$K"
printf '%-6s %-14s %-10s %-10s\n' "QBLK" "median_ms" "qps" "recall_ok"
for blk in 16 32 64 128 256; do
  out=$(SIKA_QBLK=$blk "$BIN" --basis "$BASIS" --queries "$QUERIES" \
        --n "$N" --d "$D" --q "$Q" --k "$K" --engine openmp --mode batch --reps 5)
  ms=$(echo "$out" | sed -n 's/.*median_time_ms=\([0-9.]*\).*/\1/p')
  qps=$(echo "$out" | sed -n 's/.*qps=\([0-9.]*\).*/\1/p')
  rc=$(echo "$out" | sed -n 's/.*recall_ok=\([0-9]*\).*/\1/p')
  printf '%-6s %-14s %-10s %-10s\n' "$blk" "$ms" "$qps" "$rc"
done
