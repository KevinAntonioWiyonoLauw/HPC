#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
python - <<'PY'
import importlib
for m in ["numpy","fastapi","uvicorn","httpx","pybind11","torch","sentence_transformers"]:
    try:
        mod = importlib.import_module(m)
        print(f"OK  {m:22} {getattr(mod,'__version__','?')}")
    except Exception as e:
        print(f"ERR {m:22} {type(e).__name__}: {e}")
PY
echo "--- log tail ---"
tail -n 4 results/install_py.log
echo "--- npm ---"
tail -n 3 results/npm_install.log 2>/dev/null || true
