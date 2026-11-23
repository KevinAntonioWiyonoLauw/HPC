#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
git add -A
git commit -q -m "Fase 1-2: engine OpenMP + pybind binding + service FastAPI (search/ask/engine/config/models) + korpus SIKA + web React" || echo "tidak ada perubahan baru"
echo "=== log ==="
git --no-pager log --oneline -5
echo "=== status ==="
git status -s
