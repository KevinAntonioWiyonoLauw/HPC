#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
git add -A
git commit -q -m "Fase 3-4: engine CUDA (GEMM+shared mem) & MPI (shard+Gather, exact) + recall_check + Makefile cuda/mpi" || echo "no changes"
git --no-pager log --oneline -4
