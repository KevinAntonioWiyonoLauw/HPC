#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
pip install sentence-transformers 2>&1 | tail -n 20
python - <<'PY'
import sentence_transformers, torch
print("ST", sentence_transformers.__version__, "torch", torch.__version__)
PY
