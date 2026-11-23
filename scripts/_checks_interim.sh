#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
BIN=engine/build/mpi_bench
B=data/out/basis_100000_384.bin
Qf=data/out/queries_1000_384.bin

echo "=== K7: MPI jejak memori per-proses @ N=100000 (q=100) ==="
for P in 1 2 4; do
  mpirun --allow-run-as-root --oversubscribe -np $P $BIN --basis $B --queries $Qf \
    --n 100000 --d 384 --q 100 --k 10 --reps 1 | sed "s/^/[P=$P] /"
done

echo
echo "=== K5: recall openmp vs baseline @ N=100000 (Q=1000) ==="
python scripts/recall_check.py --from-engines --basis $B --queries $Qf \
  --n 100000 --d 384 --q 1000 --k 10 --compare openmp
