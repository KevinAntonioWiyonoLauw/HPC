CXX      ?= g++
CXXFLAGS ?= -O3 -march=native -std=c++17 -Iinclude
BUILD    := build
SRC      := src

CORE           := $(SRC)/knn_util.cpp
ENGINE_BASELINE:= $(SRC)/baseline.cpp
ENGINE_OPENMP  := $(SRC)/openmp_knn.cpp

.PHONY: all bench bench_openmp clean

all: bench

$(BUILD):
	mkdir -p $(BUILD)

# --- Baseline (portabel, tanpa dependensi eksternal) ---
bench: $(BUILD)/bench_baseline
$(BUILD)/bench_baseline: bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) | $(BUILD)
	$(CXX) $(CXXFLAGS) $^ -o $@

# --- OpenMP ---
bench_openmp: $(BUILD)/bench_openmp
$(BUILD)/bench_openmp: bench/bench_main.cpp $(CORE) $(ENGINE_BASELINE) $(ENGINE_OPENMP) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fopenmp $^ -o $@

clean:
	rm -rf $(BUILD)
