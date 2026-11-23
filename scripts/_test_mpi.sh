#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika/engine
make mpi 2>&1
cd ..
source .venv/bin/activate

# dataset kecil untuk uji fungsional MPI
if [ ! -f data/out/basis_50000_384.bin ]; then
  python data/gen_synthetic.py --n 50000 --d 384 --q 200 --outdir data/out
fi

BIN=engine/build/mpi_bench
ARGS="--basis data/out/basis_50000_384.bin --queries data/out/queries_200_384.bin --n 50000 --d 384 --q 200 --k 10 --reps 3"

for P in 1 2 4; do
  echo "===== mpirun -np $P ====="
  mpirun --allow-run-as-root --oversubscribe -np $P $BIN $ARGS --dump results/raw/mpi_P${P}.idx
done

echo "=== exactness: P=1 vs P=2 vs P=4 (harus identik) ==="
python - <<'PY'
import numpy as np
a=np.fromfile("results/raw/mpi_P1.idx",dtype=np.int32)
b=np.fromfile("results/raw/mpi_P2.idx",dtype=np.int32)
c=np.fromfile("results/raw/mpi_P4.idx",dtype=np.int32)
print("P1==P2:", np.array_equal(np.sort(a.reshape(-1,10),1), np.sort(b.reshape(-1,10),1)))
print("P1==P4:", np.array_equal(np.sort(a.reshape(-1,10),1), np.sort(c.reshape(-1,10),1)))
PY
