#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}

echo "=== rebuild bench_openmp + bench_cuda ==="
( cd engine && make bench_openmp bench_cuda 2>&1 | tail -3 ) || true

echo
echo "=== K5: recall cuda single-query vs baseline (N=50000) ==="
if [ ! -f data/out/queries_300_384.bin ]; then
  python data/gen_synthetic.py --n 50000 --d 384 --q 300 --outdir data/out >/dev/null
fi
engine/build/bench_cuda --basis data/out/basis_50000_384.bin --queries data/out/queries_300_384.bin \
  --n 50000 --d 384 --q 300 --k 10 --engine cuda --mode single-query --reps 1

echo
echo "=== K7: MPI jejak memori @ N=500000 (skala Tabel 4.2, q=100) ==="
if [ ! -f data/out/basis_500000_384.bin ]; then
  echo "generate N=500000 (768MB)..."
  python data/gen_synthetic.py --n 500000 --d 384 --q 100 --outdir data/out
fi
for P in 1 4; do
  echo "-- P=$P --"
  mpirun --allow-run-as-root --oversubscribe -np $P engine/build/mpi_bench \
    --basis data/out/basis_500000_384.bin --queries data/out/queries_100_384.bin \
    --n 500000 --d 384 --q 100 --k 10 --reps 1
done
