// knn_util.cpp — implementasi utilitas bersama
#include "knn_util.h"
#include <cstdio>
#include <limits>
#include <map>
#include <stdexcept>

namespace knn {

// ---------- Top-k bounded max-heap per query ----------
// Layout out: q * k. Setiap query punya heap sendiri pada slice out[qi*k..).
// KHeap menjaga max-heap berukuran <= k (h_[0] = elemen terjauh saat ini).
void topk_reset(std::vector<Neighbor>& out, std::size_t q, std::size_t k) {
    out.assign(q * k, Neighbor{-1, std::numeric_limits<float>::infinity()});
}

static inline void heap_sift_down(Neighbor* h, std::size_t n, std::size_t i) {
    while (true) {
        std::size_t l = 2 * i + 1, r = 2 * i + 2, largest = i;
        if (l < n && h[l].dist2 > h[largest].dist2) largest = l;
        if (r < n && h[r].dist2 > h[largest].dist2) largest = r;
        if (largest == i) break;
        std::swap(h[i], h[largest]);
        i = largest;
    }
}

void KHeap::push(std::int32_t idx, float dist2) {
    if (n_ < k_) {
        h_[n_] = Neighbor{idx, dist2};
        std::size_t i = n_++;
        while (i > 0) {
            std::size_t p = (i - 1) / 2;
            if (h_[p].dist2 < h_[i].dist2) { std::swap(h_[p], h_[i]); i = p; }
            else break;
        }
    } else if (dist2 < h_[0].dist2) {
        h_[0] = Neighbor{idx, dist2};
        heap_sift_down(h_, n_, 0);
    }
}

void KHeap::finalize() {
    std::sort(h_, h_ + k_,
              [](const Neighbor& a, const Neighbor& b) { return a.dist2 < b.dist2; });
}

// ---------- Loader ----------
bool load_bin_f32(const std::string& path, std::vector<float>& data) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    std::fseek(f, 0, SEEK_END);
    long bytes = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    if (bytes < 0 || (bytes % 4) != 0) { std::fclose(f); return false; }
    data.resize(static_cast<std::size_t>(bytes) / 4);
    std::size_t got = data.empty() ? 0 : std::fread(data.data(), 4, data.size(), f);
    std::fclose(f);
    return got == data.size();
}

// ---------- Recall check ----------
bool same_neighbor_sets(const std::vector<Neighbor>& a,
                        const std::vector<Neighbor>& b,
                        std::size_t q, std::size_t k) {
    if (a.size() != b.size()) return false;
    for (std::size_t qi = 0; qi < q; ++qi) {
        std::vector<std::int32_t> ia, ib;
        ia.reserve(k); ib.reserve(k);
        for (std::size_t j = 0; j < k; ++j) {
            ia.push_back(a[qi * k + j].index);
            ib.push_back(b[qi * k + j].index);
        }
        std::sort(ia.begin(), ia.end());
        std::sort(ib.begin(), ib.end());
        if (ia != ib) return false;
    }
    return true;
}

// ---------- Percentiles ----------
void percentiles(std::vector<double> samples, double& p50, double& p95,
                 double& p99) {
    p50 = p95 = p99 = 0.0;
    if (samples.empty()) return;
    std::sort(samples.begin(), samples.end());
    auto pick = [&](double p) {
        std::size_t idx = static_cast<std::size_t>(p * (samples.size() - 1) + 0.5);
        if (idx >= samples.size()) idx = samples.size() - 1;
        return samples[idx];
    };
    p50 = pick(0.50);
    p95 = pick(0.95);
    p99 = pick(0.99);
}

// ---------- Registry engine ----------
static std::map<std::string, KnnSearchFn>& registry() {
    static std::map<std::string, KnnSearchFn> r;
    return r;
}
void register_engine(const std::string& name, KnnSearchFn fn) {
    registry()[name] = fn;
}
KnnSearchFn find_engine(const std::string& name) {
    auto& r = registry();
    auto it = r.find(name);
    return it == r.end() ? nullptr : it->second;
}
std::vector<std::string> engine_names() {
    std::vector<std::string> names;
    for (auto& kv : registry()) names.push_back(kv.first);
    return names;
}

}  // namespace knn
