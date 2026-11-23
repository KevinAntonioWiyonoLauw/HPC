#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
LOG=results/install_py.log
{
  echo "=== upgrade pip + install requirements ==="
  pip install --upgrade pip
  pip install -r service/requirements.txt
  echo "=== install torch CPU + sentence-transformers ==="
  pip install torch --index-url https://download.pytorch.org/whl/cpu
  pip install sentence-transformers
  echo "=== versi ==="
  python - <<'PY'
import importlib
for m in ["fastapi","uvicorn","httpx","numpy","pybind11","sentence_transformers","torch"]:
    try:
        mod=importlib.import_module(m); print(m, getattr(mod,"__version__","?"))
    except Exception as e:
        print(m,"ERR",e)
PY
  echo "=== DONE ==="
} > "$LOG" 2>&1
echo "selesai, lihat $LOG"
