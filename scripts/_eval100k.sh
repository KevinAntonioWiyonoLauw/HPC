#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
python scripts/evaluate_all.py --n 100000 --d 384 --q 1000 --k 10 --reps 3
