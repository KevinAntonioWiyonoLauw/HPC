// bench_main.cpp — harness benchmark engine k-NN
// Mengukur latensi batch & per-query, QPS, persentil, dan validasi recall
// terhadap baseline exact (K5). Keluaran: ringkasan ke stdout + baris CSV.
#include "knn_engine.h"
#include "knn_util.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

struct Args {
    std::string basis, queries, engine = "baseline", mode = "batch", out;
    std::size_t n = 0, d = 0, q = 0, k = 10, reps = 3;
    bool list = false;
};

bool parse(int argc, char** argv, Args& a) {
    for (int i = 1; i < argc; ++i) {
        std::string s = argv[i];
        auto need = [&](const char* name) -> std::string {
            if (i + 1 >= argc) { std::fprintf(stderr, "arg %s butuh nilai\n", name); std::exit(2); }
            return argv[++i];
        };
        if (s == "--basis") a.basis = need("--basis");
        else if (s == "--queries") a.queries = need("--queries");
        else if (s == "--engine") a.engine = need("--engine");
        else if (s == "--mode") a.mode = need("--mode");
        else if (s == "--out") a.out = need("--out");
        else if (s == "--n") a.n = std::stoull(need("--n"));
        else if (s == "--d") a.d = std::stoull(need("--d"));
        else if (s == "--q") a.q = std::stoull(need("--q"));
        else if (s == "--k") a.k = std::stoull(need("--k"));
        else if (s == "--reps") a.reps = std::stoull(need("--reps"));
        else if (s == "--list") a.list = true;
        else { std::fprintf(stderr, "arg tidak dikenal: %s\n", s.c_str()); return false; }
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    Args a;
    if (!parse(argc, argv, a)) return 2;

    if (a.list) {
        for (auto& nm : knn::engine_names()) std::printf("%s\n", nm.c_str());
        return 0;
    }

    if (a.basis.empty() || a.queries.empty()) {
        std::fprintf(stderr, "wajib: --basis <file> --queries <file> [--n --d --q --k]\n");
        return 2;
    }

    std::vector<float> basis, queries;
    if (!knn::load_bin_f32(a.basis, basis)) { std::fprintf(stderr, "gagal baca basis\n"); return 1; }
    if (!knn::load_bin_f32(a.queries, queries)) { std::fprintf(stderr, "gagal baca queries\n"); return 1; }

    // Infer n,d,q dari ukuran file bila tidak diberikan.
    if (a.d == 0) {
        // tebak dari queries & basis bila memungkinkan: d = queries.size()/q
        std::fprintf(stderr, "--d wajib diisi\n"); return 2;
    }
    if (a.n == 0) a.n = basis.size() / a.d;
    if (a.q == 0) a.q = queries.size() / a.d;
    if (basis.size() < a.n * a.d || queries.size() < a.q * a.d) {
        std::fprintf(stderr, "ukuran file tidak konsisten dengan n/d/q\n"); return 2;
    }

    KnnSearchFn fn = knn::find_engine(a.engine);
    if (!fn) { std::fprintf(stderr, "engine '%s' tidak terdaftar\n", a.engine.c_str()); return 2; }

    QueryBatch batch{queries.data(), a.q, a.d};

    // --- Referensi baseline untuk recall (K5) ---
    std::vector<Neighbor> ref;
    bool have_ref = true;
    if (a.engine != "baseline") {
        KnnSearchFn base = knn::find_engine("baseline");
        if (base) base(basis.data(), a.n, batch, a.k, ref);
        else have_ref = false;
    }

    // --- Pengukuran ---
    std::vector<double> per_query_ms;      // sampel latensi per-query (single-query mode)
    std::vector<double> rep_total_ms;      // total waktu per rep (batch mode)
    std::vector<Neighbor> out;
    bool recall_ok = true;

    if (a.mode == "single-query") {
        // Q query dijalankan bergantian, tiap query diukur sendiri.
        per_query_ms.reserve(a.q * a.reps);
        double total_all = 0.0;
        for (std::size_t rep = 0; rep < a.reps; ++rep) {
            for (std::size_t qi = 0; qi < a.q; ++qi) {
                QueryBatch one{queries.data() + qi * a.d, 1, a.d};
                knn::Timer t;
                fn(basis.data(), a.n, one, a.k, out);
                per_query_ms.push_back(t.elapsed_ms());
            }
            total_all += 0.0;
        }
        if (have_ref && !ref.empty()) recall_ok = knn::same_neighbor_sets(out, ref, a.q, a.k);
    } else {
        // batch: ukur total per rep, ambil median
        for (std::size_t rep = 0; rep < a.reps; ++rep) {
            knn::Timer t;
            fn(basis.data(), a.n, batch, a.k, out);
            rep_total_ms.push_back(t.elapsed_ms());
        }
        if (have_ref && !ref.empty()) recall_ok = knn::same_neighbor_sets(out, ref, a.q, a.k);
    }

    // --- Ringkasan ---
    double median_total = 0.0, qps = 0.0, p50 = 0, p95 = 0, p99 = 0;
    if (a.mode == "single-query") {
        double sum = 0; for (double v : per_query_ms) sum += v;
        double mean_ms = per_query_ms.empty() ? 0 : sum / per_query_ms.size();
        qps = mean_ms > 0 ? 1000.0 / mean_ms : 0.0;  // throughput per-query (1 stream)
        knn::percentiles(per_query_ms, p50, p95, p99);
        median_total = mean_ms;
    } else {
        std::vector<double> sorted = rep_total_ms;
        std::sort(sorted.begin(), sorted.end());
        median_total = sorted[sorted.size() / 2];
        qps = median_total > 0 ? (a.q * 1000.0) / median_total : 0.0;
    }

    std::printf("engine=%s n=%zu d=%zu q=%zu k=%zu mode=%s reps=%zu\n",
                a.engine.c_str(), a.n, a.d, a.q, a.k, a.mode.c_str(), a.reps);
    std::printf("median_time_ms=%.3f qps=%.2f p50=%.3f p95=%.3f p99=%.3f recall_ok=%d\n",
                median_total, qps, p50, p95, p99, recall_ok ? 1 : 0);

    if (!a.out.empty()) {
        bool newfile = false;
        FILE* probe = std::fopen(a.out.c_str(), "r");
        if (!probe) newfile = true; else std::fclose(probe);
        FILE* f = std::fopen(a.out.c_str(), "a");
        if (!f) { std::fprintf(stderr, "gagal buka %s\n", a.out.c_str()); return 1; }
        if (newfile)
            std::fprintf(f, "engine,n,d,q,k,mode,reps,median_time_ms,qps,p50_ms,p95_ms,p99_ms,recall_ok\n");
        std::fprintf(f, "%s,%zu,%zu,%zu,%zu,%s,%zu,%.3f,%.2f,%.3f,%.3f,%.3f,%d\n",
                     a.engine.c_str(), a.n, a.d, a.q, a.k, a.mode.c_str(), a.reps,
                     median_total, qps, p50, p95, p99, recall_ok ? 1 : 0);
        std::fclose(f);
    }
    return 0;
}
