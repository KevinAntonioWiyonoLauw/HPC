#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
export HF_HUB_DISABLE_TELEMETRY=1
python scripts/build_corpus.py --sop-dir data/sop_synthetic --outdir data/embeddings --name sika --filler 20000
ls -la data/embeddings/
