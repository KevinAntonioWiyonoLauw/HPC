#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
B=data/out/basis_50000_384.bin; Q=data/out/queries_300_384.bin
echo "=== cuda BATCH (Q=300) ==="
engine/build/bench_cuda --basis $B --queries $Q --n 50000 --d 384 --q 300 --k 10 --engine cuda --mode batch --reps 1
echo "=== cuda SINGLE (Q=300) ==="
engine/build/bench_cuda --basis $B --queries $Q --n 50000 --d 384 --q 300 --k 10 --engine cuda --mode single-query --reps 1
echo "=== baseline BATCH ==="
engine/build/bench_cuda --basis $B --queries $Q --n 50000 --d 384 --q 300 --k 10 --engine baseline --mode batch --reps 1
