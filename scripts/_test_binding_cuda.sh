#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
python - <<'PY'
import sys, time
sys.path.insert(0, "service")
import numpy as np, sika_engine
eng = sika_engine.SikaEngine()
eng.load_basis_file("data/out/basis_50000_384.bin", 50000, 384)
print("engines =", eng.engines())
rng = np.random.default_rng(1)
q = rng.uniform(0,1,size=(50,384)).astype(np.float32)
ib,_ = eng.search("baseline", q, 10); ib=np.asarray(ib)
for name in eng.engines():
    t=time.perf_counter(); idx,_=eng.search(name,q,10); dt=(time.perf_counter()-t)*1000
    same = np.array_equal(np.sort(ib,1), np.sort(np.asarray(idx),1))
    print(f"{name:9} {dt:8.2f} ms  recall_identik={same}")
PY
