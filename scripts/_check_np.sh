#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
python - <<'PY'
import numpy as np
print("numpy ok", np.__version__)
PY
