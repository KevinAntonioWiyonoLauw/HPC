#!/usr/bin/env bash
# Bangun modul Python (pybind11) service/sika_engine*.so.
# Portabel: berpindah ke root repo berdasarkan lokasi skrip, dan hanya
# mengaktifkan .venv bila ada (di CI venv diaktifkan oleh langkah sebelumnya).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -f ".venv/bin/activate" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

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
