// openmp_knn.cpp — Exact k-NN: paralelisasi query + SIMD + cache blocking
//
// Strategi:
//  1. Loop-Level Parallelism : paralelisasi atas blok query (schedule dynamic)
//  2. SIMD                   : #pragma omp simd pada loop dimensi
//  3. Cache Blocking (tiling): tiap baris basis dibaca sekali lalu dipakai ulang
//     untuk QBLK query sekaligus -> mengurangi traffic basis dari Q pass menjadi
//     (Q/QBLK) pass, menjaga working set tetap ramah cache.
#include "knn_engine.h"
#include "knn_util.h"

#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <vector>

namespace {

constexpr std::size_t QBLK_DEFAULT = 128;  // jumlah query per blok (tiling)

// Ukuran blok dapat diatur lewat env SIKA_QBLK. Nilai bawaan 128 dipilih dari
// sapuan (scripts/bench_qblk.sh) pada N=100k: D=384 blok 128 tercepat & stabil
// (~1031 ms) dibanding 16/64; D=768 semua ukuran setara sehingga 128 aman.
// Dibaca sekali lalu di-cache.
static std::size_t qblk() {
    static const std::size_t v = [] {
        const char* e = std::getenv("SIKA_QBLK");
        if (e) {
            long x = std::atol(e);
            if (x > 0) return static_cast<std::size_t>(x);
        }
        return QBLK_DEFAULT;
    }();
    return v;
}

int openmp_search(const float* basis, std::size_t n, const QueryBatch& batch,
                  std::size_t k, std::vector<Neighbor>& out) {
    const std::size_t Q = batch.q, D = batch.d;
    const std::size_t QBLK = qblk();
    knn::topk_reset(out, Q, k);

#pragma omp parallel for schedule(dynamic)
    for (std::size_t qb = 0; qb < Q; qb += QBLK) {
        const std::size_t qend = std::min(qb + QBLK, Q);
        // heap per query pada blok ini
        std::vector<knn::KHeap> heaps;
        heaps.reserve(qend - qb);
        for (std::size_t qi = qb; qi < qend; ++qi)
            heaps.emplace_back(out.data() + qi * k, k);

        for (std::size_t j = 0; j < n; ++j) {
            const float* p = basis + j * D;  // baris basis dibaca sekali
            for (std::size_t qi = qb; qi < qend; ++qi) {
                const float* q = batch.data + qi * D;
                float d2 = 0.0f;
#pragma omp simd reduction(+ : d2)
                for (std::size_t d = 0; d < D; ++d) {
                    const float t = q[d] - p[d];
                    d2 += t * t;
                }
                heaps[qi - qb].push(static_cast<std::int32_t>(j), d2);
            }
        }
        for (std::size_t qi = qb; qi < qend; ++qi) heaps[qi - qb].finalize();
    }
    return 0;
}

}  // namespace

namespace knn {
static const struct OpenMPRegistrar {
    OpenMPRegistrar() { register_engine("openmp", openmp_search); }
} g_openmp_registrar;
}  // namespace knn
