#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika/engine
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
B=../data/out/basis_100000_384.bin
Q=../data/out/queries_1000_384.bin

echo "=== CUDA smoke correctness (N=10000) ==="
if [ ! -f ../data/out/basis_10000_384.bin ]; then
  ( cd .. && source .venv/bin/activate && python data/gen_synthetic.py --n 10000 --d 384 --q 200 --outdir data/out >/dev/null )
fi
./build/bench_cuda --basis ../data/out/basis_10000_384.bin --queries ../data/out/queries_200_384.bin \
  --n 10000 --d 384 --q 200 --k 10 --engine cuda --mode batch --reps 2

echo
echo "=== K2: CUDA batch speedup @ N=100000 Q=1000 ==="
echo "-- baseline --"
./build/bench_cuda --basis $B --queries $Q --n 100000 --d 384 --q 1000 --k 10 --engine baseline --mode batch --reps 3
echo "-- cuda --"
./build/bench_cuda --basis $B --queries $Q --n 100000 --d 384 --q 1000 --k 10 --engine cuda --mode batch --reps 3

echo
echo "=== K3: CUDA single-query p95 @ N=100000 Q=1000 ==="
./build/bench_cuda --basis $B --queries $Q --n 100000 --d 384 --q 1000 --k 10 --engine cuda --mode single-query --reps 1
