// baseline.cpp — Exact k-NN sekuensial CPU single-thread (acuan pembanding)
#include "knn_engine.h"
#include "knn_util.h"

namespace {

int baseline_search(const float* basis, std::size_t n, const QueryBatch& batch,
                    std::size_t k, std::vector<Neighbor>& out) {
    knn::topk_reset(out, batch.q, k);
    for (std::size_t qi = 0; qi < batch.q; ++qi) {
        const float* q = batch.data + qi * batch.d;
        knn::KHeap heap(out.data() + qi * k, k);
        for (std::size_t j = 0; j < n; ++j) {
            const float* p = basis + j * batch.d;
            float d2 = 0.0f;
            for (std::size_t d = 0; d < batch.d; ++d) {
                const float t = q[d] - p[d];
                d2 += t * t;
            }
            heap.push(static_cast<std::int32_t>(j), d2);
        }
        heap.finalize();
    }
    return 0;
}

}  // namespace

namespace knn {
static const struct BaselineRegistrar {
    BaselineRegistrar() { register_engine("baseline", baseline_search); }
} g_baseline_registrar;
}  // namespace knn
