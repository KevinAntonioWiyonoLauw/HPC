#!/usr/bin/env bash
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika/engine
echo "=== default ==="
./build/cuda_diag
echo "=== dengan LD_LIBRARY_PATH=/usr/lib/wsl/lib ==="
LD_LIBRARY_PATH=/usr/lib/wsl/lib ./build/cuda_diag
echo "=== mana libcuda yang dipakai (ldd) ==="
ldd ./build/cuda_diag | grep -E "libcuda|libcublas"
