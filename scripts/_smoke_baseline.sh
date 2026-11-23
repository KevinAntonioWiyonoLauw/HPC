#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

python data/gen_synthetic.py --n 5000 --d 384 --q 100 --outdir data/out

BIN=engine/build/bench_baseline
echo "--- batch ---"
$BIN --basis data/out/basis_5000_384.bin --queries data/out/queries_100_384.bin \
     --n 5000 --d 384 --q 100 --k 10 --engine baseline --mode batch --reps 3

echo "--- single-query ---"
$BIN --basis data/out/basis_5000_384.bin --queries data/out/queries_100_384.bin \
     --n 5000 --d 384 --q 100 --k 10 --engine baseline --mode single-query --reps 1
