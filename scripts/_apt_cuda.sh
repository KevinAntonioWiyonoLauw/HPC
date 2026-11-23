#!/usr/bin/env bash
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
LOG=/mnt/g/Project/Kuliah/HPC/hpc-knn-sika/results/apt_cuda.log
{
  echo "=== install nvidia-cuda-toolkit (nvcc) ==="
  apt-get install -y nvidia-cuda-toolkit
  echo "=== versi ==="
  nvcc --version
  echo "=== DONE ==="
} > "$LOG" 2>&1
echo "selesai -> $LOG"
