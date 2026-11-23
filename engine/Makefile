CXX      ?= g++
NVCC     ?= nvcc
MPICXX   ?= mpic++
CXXFLAGS ?= -O3 -march=native -std=c++17 -Iinclude
NVFLAGS  ?= -O3 -std=c++17 -Iinclude -gencode arch=compute_75,code=sm_75 --expt-relaxed-constexpr -Xcompiler -fPIC
BUILD    := build
SRC      := src

CORE           := $(SRC)/knn_util.cpp
ENGINE_BASELINE:= $(SRC)/baseline.cpp
ENGINE_OPENMP  := $(SRC)/openmp_knn.cpp
ENGINE_CUDA    := $(SRC)/cuda_knn.cu

.PHONY: all bench bench_openmp bench_cuda mpi clean

all: bench bench_openmp

$(BUILD):
	mkdir -p $(BUILD)

# --- Baseline (portabel) ---
bench: $(BUILD)/bench_baseline
$(BUILD)/bench_baseline: bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) | $(BUILD)
	$(CXX) $(CXXFLAGS) $^ -o $@

# --- OpenMP ---
bench_openmp: $(BUILD)/bench_openmp
$(BUILD)/bench_openmp: bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) $(ENGINE_OPENMP) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fopenmp $^ -o $@

# --- CUDA (butuh nvcc + GPU NVIDIA) ---
bench_cuda: $(BUILD)/bench_cuda
$(BUILD)/cuda_knn.o: $(ENGINE_CUDA) include/knn_engine.h include/knn_util.h | $(BUILD)
	$(NVCC) $(NVFLAGS) -c $< -o $@
$(BUILD)/bench_cuda: bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) $(BUILD)/cuda_knn.o | $(BUILD)
	$(CXX) $(CXXFLAGS) bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) $(BUILD)/cuda_knn.o -o $@ -L/usr/local/cuda/lib64 -lcudart -lcublas

# --- MPI standalone ---
mpi: $(BUILD)/mpi_bench
$(BUILD)/mpi_bench: bench/mpi_bench.cpp $(CORE) | $(BUILD)
	$(MPICXX) $(CXXFLAGS) bench/mpi_bench.cpp $(CORE) -o $@

clean:
	rm -rf $(BUILD)
