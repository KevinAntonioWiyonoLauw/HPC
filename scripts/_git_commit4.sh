#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
git add -A
git commit -q -m "Fase 3: CUDA GEMM(cuBLAS)+refine eksak (K2 245x, K3 2.6ms, recall 100%); binding+cuda; evaluate_all K1-K7 semua PASS; perbaikan recall single-query & LD_LIBRARY_PATH wsl" || echo "no changes"
git --no-pager log --oneline -6
