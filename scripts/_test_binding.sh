#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
python - <<'PY'
import sys, time
sys.path.insert(0, "service")
import numpy as np
import sika_engine

eng = sika_engine.SikaEngine()
eng.load_basis_file("data/out/basis_5000_384.bin", 5000, 384)
print("n,d =", eng.n, eng.d, "engines =", eng.engines())

rng = np.random.default_rng(0)
q = rng.uniform(0, 1, size=(3, 384)).astype(np.float32)

for name in eng.engines():
    t = time.perf_counter()
    idx, dist = eng.search(name, q, 10)
    dt = (time.perf_counter() - t) * 1000
    print(f"{name:9} -> idx.shape={idx.shape} top1={idx[0,:3].tolist()} dist1={dist[0,0]:.4f} ({dt:.2f} ms)")

# cek recall baseline vs openmp identik
ib, _ = eng.search("baseline", q, 10)
io, _ = eng.search("openmp", q, 10)
print("recall identik baseline==openmp:", np.array_equal(np.sort(ib, axis=1), np.sort(io, axis=1)))
PY
