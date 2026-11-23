#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

INC=$(python -m pybind11 --includes)
EXT=$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
OUT="service/sika_engine${EXT}"

# Engine yang ditautkan: baseline + openmp (cuda/mpi ditambahkan pada fase berikutnya)
SRCS="engine/bindings/pybind_module.cpp engine/src/knn_util.cpp engine/src/baseline.cpp engine/src/openmp_knn.cpp"

echo "Building $OUT"
g++ -O3 -march=native -std=c++17 -fopenmp -shared -fPIC \
    $INC -Iengine/include \
    $SRCS -o "$OUT"

echo "OK -> $OUT"
