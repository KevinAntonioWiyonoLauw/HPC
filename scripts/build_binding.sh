#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

INC=$(python -m pybind11 --includes)
EXT=$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
OUT="service/sika_engine${EXT}"

# Engine yang ditautkan: baseline + openmp (+ cuda bila objeknya tersedia)
SRCS="engine/bindings/pybind_module.cpp engine/src/knn_util.cpp engine/src/baseline.cpp engine/src/openmp_knn.cpp"
CUDA_OBJ="engine/build/cuda_knn.o"
EXTRA_LIB=""
if [ -f "$CUDA_OBJ" ]; then
  SRCS="$SRCS $CUDA_OBJ"
  EXTRA_LIB="-L/usr/local/cuda/lib64 -lcudart -lcublas"
  echo "Termasuk engine CUDA"
else
  echo "Tanpa engine CUDA (objek belum dibangun)"
fi

echo "Building $OUT"
g++ -O3 -march=native -std=c++17 -fopenmp -shared -fPIC \
    $INC -Iengine/include \
    $SRCS -o "$OUT" $EXTRA_LIB

echo "OK -> $OUT"
