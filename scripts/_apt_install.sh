#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
LOG=/mnt/g/Project/Kuliah/HPC/hpc-knn-sika/results/apt_install.log
{
  echo "=== apt update ==="
  apt-get update -qq
  echo "=== install cmake + mpi ==="
  apt-get install -y -qq cmake libopenmpi-dev openmpi-bin
  echo "=== install cuda toolkit (bisa lama) ==="
  apt-get install -y -qq nvidia-cuda-toolkit
  echo "=== versi ==="
  cmake --version | head -1
  mpicc --version | head -1
  nvcc --version | tail -2
  echo "=== DONE ==="
} > "$LOG" 2>&1
echo "apt install selesai -> $LOG"
