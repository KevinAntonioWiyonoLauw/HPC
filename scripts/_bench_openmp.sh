#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

# dataset uji menengah (kalau belum ada)
if [ ! -f data/out/basis_100000_384.bin ]; then
  python data/gen_synthetic.py --n 100000 --d 384 --q 1000 --outdir data/out
fi

echo "=== OpenMP matrix: N=100000 D=384 Q=1000 k=10 (batch) ==="
python scripts/run_bench_matrix.py \
  --basis data/out/basis_100000_384.bin \
  --queries data/out/queries_1000_384.bin \
  --n 100000 --d 384 --q 1000 --k 10 \
  --threads 1 2 4 --reps 3 --mode batch
