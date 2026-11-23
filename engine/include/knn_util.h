// knn_util.h — utilitas bersama: timer, top-k (bounded max-heap), loader .bin
#pragma once
#include "knn_engine.h"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <string>
#include <vector>

namespace knn {

// ---- Timer beresolusi tinggi (std::chrono) ----
class Timer {
public:
    Timer() { reset(); }
    void reset() { t0_ = std::chrono::high_resolution_clock::now(); }
    double elapsed_ms() const {
        auto t1 = std::chrono::high_resolution_clock::now();
        return std::chrono::duration<double, std::milli>(t1 - t0_).count();
    }
private:
    std::chrono::high_resolution_clock::time_point t0_;
};

// ---- Top-k terbatas (bounded max-heap) ----
// Isi out (ukuran q*k) dengan dist2 = inf sebagai nilai awal.
void topk_reset(std::vector<Neighbor>& out, std::size_t q, std::size_t k);

// KHeap: max-heap berukuran <= k yang bekerja pada slice out[qi*k .. qi*k+k).
// push() O(log k); finalize() mengurutkan menaik menurut dist2.
class KHeap {
public:
    KHeap(Neighbor* base, std::size_t k) : h_(base), k_(k), n_(0) {}
    void push(std::int32_t idx, float dist2);
    void finalize();
    std::size_t size() const { return n_; }
private:
    Neighbor*   h_;
    std::size_t k_;
    std::size_t n_;
};

// ---- Loader matriks float32 row-major dari file .bin mentah ----
// Membaca seluruh isi file ke data (jumlah float = ukuran_file/4).
bool load_bin_f32(const std::string& path, std::vector<float>& data);

// ---- Self-check correctness: himpunan indeks per query identik ----
bool same_neighbor_sets(const std::vector<Neighbor>& a,
                        const std::vector<Neighbor>& b,
                        std::size_t q, std::size_t k);

// p50/p95/p99 dari sampel (ms)
void percentiles(std::vector<double> samples, double& p50, double& p95,
                 double& p99);

// ---- Registry engine (untuk bench multi-engine & binding) ----
void register_engine(const std::string& name, KnnSearchFn fn);
KnnSearchFn find_engine(const std::string& name);  // nullptr bila tidak ada
std::vector<std::string> engine_names();

}  // namespace knn
