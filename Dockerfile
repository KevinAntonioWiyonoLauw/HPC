# ============================================================================
# SIKA backend — build engine k-NN (baseline/openmp/cuda) + pybind + FastAPI
# Multi-stage: builder (CUDA devel, ada nvcc) -> runtime (CUDA runtime, ada cuBLAS)
# ============================================================================
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ make cmake python3 python3-dev python3-venv python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Python venv + dependensi ---
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy pybind11 && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" httpx python-dotenv pydantic sentence-transformers

# --- Pra-unduh model embedding (MiniLM) agar runtime tidak butuh internet ---
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

WORKDIR /src
COPY engine ./engine
COPY service ./service

# --- Build engine (openmp + cuda) lalu pybind binding ---
RUN cd engine && make bench_openmp bench_cuda && cd .. && \
    EXT=$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))') && \
    g++ -O3 -march=native -std=c++17 -fopenmp -shared -fPIC \
        $(python -m pybind11 --includes) -Iengine/include \
        engine/bindings/pybind_module.cpp engine/src/knn_util.cpp \
        engine/src/baseline.cpp engine/src/openmp_knn.cpp engine/build/cuda_knn.o \
        -o "service/sika_engine${EXT}" \
        -L/usr/local/cuda/lib64 -lcudart -lcublas

# ============================================================================
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
ENV PATH=/opt/venv/bin:$PATH
ENV HF_HOME=/opt/hf
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
ENV OMP_NUM_THREADS=4
ENV DATA_DIR=./data

WORKDIR /app
COPY --from=builder /src/service /app/service

EXPOSE 8000
WORKDIR /app/service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
