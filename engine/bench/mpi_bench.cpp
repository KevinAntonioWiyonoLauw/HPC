// mpi_bench.cpp — Exact k-NN terdistribusi (MPI): sharding + Gather top-k.
//
// Tiap rank HANYA memuat shard barisnya sendiri dari file (seek offset), sehingga
// jejak memori per proses ~ N/P (dasar kriteria K7). Setiap rank menghitung
// top-k lokal atas shard-nya, lalu MPI_Gather mengumpulkan kandidat ke rank 0
// yang menggabungkannya menjadi top-k global yang eksak (partisi disjoint).
//
// Bangun: mpic++ -O3 -std=c++17 -Iinclude bench/mpi_bench.cpp src/knn_util.cpp -o build/mpi_bench
// Jalankan: mpirun --oversubscribe -np 4 ./build/mpi_bench --basis ... --queries ... --n N --d D --q Q --k 10 --reps 3
#include "knn_engine.h"
#include "knn_util.h"

#include <mpi.h>

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

long vm_rss_kb() {
    FILE* f = std::fopen("/proc/self/status", "r");
    if (!f) return -1;
    char line[256];
    long kb = -1;
    while (std::fgets(line, sizeof(line), f)) {
        if (std::strncmp(line, "VmRSS:", 6) == 0) {
            std::sscanf(line + 6, "%ld", &kb);
            break;
        }
    }
    std::fclose(f);
    return kb;
}

}  // namespace

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank = 0, size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    std::string basis_path, queries_path, dump_path;
    std::size_t N = 0, D = 0, Q = 0, K = 10, reps = 3;
    for (int i = 1; i < argc; ++i) {
        std::string s = argv[i];
        auto nx = [&]() { return std::string(argv[++i]); };
        if (s == "--basis") basis_path = nx();
        else if (s == "--queries") queries_path = nx();
        else if (s == "--n") N = std::stoull(nx());
        else if (s == "--d") D = std::stoull(nx());
        else if (s == "--q") Q = std::stoull(nx());
        else if (s == "--k") K = std::stoull(nx());
        else if (s == "--reps") reps = std::stoull(nx());
        else if (s == "--dump") dump_path = nx();
    }
    if (N == 0 || D == 0 || Q == 0 || basis_path.empty() || queries_path.empty()) {
        if (rank == 0) std::fprintf(stderr, "arg kurang (--basis --queries --n --d --q)\n");
        MPI_Finalize();
        return 2;
    }

    // queries dimuat penuh di semua rank (kecil)
    std::vector<float> queries;
    if (!knn::load_bin_f32(queries_path, queries)) {
        if (rank == 0) std::fprintf(stderr, "gagal baca queries\n");
        MPI_Finalize();
        return 1;
    }

    // pembagian baris: shard kontigu per rank
    std::size_t base = N / size, rem = N % size;
    std::size_t r0 = rank * base + std::min<std::size_t>(rank, rem);
    std::size_t cnt = base + (static_cast<std::size_t>(rank) < rem ? 1 : 0);

    // baca shard (seek offset), hanya baris milik rank ini
    std::vector<float> shard(cnt * D);
    {
        FILE* f = std::fopen(basis_path.c_str(), "rb");
        if (!f) { if (rank == 0) std::fprintf(stderr, "gagal buka basis\n"); MPI_Finalize(); return 1; }
        long off = static_cast<long>(r0 * D * sizeof(float));
        std::fseek(f, off, SEEK_SET);
        std::size_t got = std::fread(shard.data(), sizeof(float), cnt * D, f);
        std::fclose(f);
        if (got != cnt * D) { if (rank == 0) std::fprintf(stderr, "shard fread short\n"); MPI_Finalize(); return 1; }
    }

    long rss_kb = vm_rss_kb();

    // buffer hasil lokal (Q x K) dan global
    std::vector<Neighbor> local(Q * K), gathered;
    std::vector<double> compute_times;

    for (std::size_t rep = 0; rep < reps; ++rep) {
        MPI_Barrier(MPI_COMM_WORLD);
        double t0 = MPI_Wtime();
        knn::topk_reset(local, Q, K);
        for (std::size_t qi = 0; qi < Q; ++qi) {
            const float* q = queries.data() + qi * D;
            knn::KHeap heap(local.data() + qi * K, K);
            for (std::size_t j = 0; j < cnt; ++j) {
                const float* p = shard.data() + j * D;
                float d2 = 0.f;
                for (std::size_t d = 0; d < D; ++d) { float t = q[d] - p[d]; d2 += t * t; }
                heap.push(static_cast<std::int32_t>(r0 + j), d2);
            }
            heap.finalize();
        }
        double t1 = MPI_Wtime();
        compute_times.push_back((t1 - t0) * 1000.0);
    }

    // Gather semua kandidat ke rank 0 (jumlah byte eksplisit!)
    const int gather_count = static_cast<int>(Q * K * sizeof(Neighbor));
    gathered.resize(Q * K * size);
    MPI_Gather(local.data(), gather_count, MPI_BYTE,
               gathered.data(), gather_count, MPI_BYTE, 0, MPI_COMM_WORLD);

    // kumpulkan memori per rank
    long max_rss = 0;
    MPI_Reduce(&rss_kb, &max_rss, 1, MPI_LONG, MPI_MAX, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        std::vector<double> sorted = compute_times;
        std::sort(sorted.begin(), sorted.end());
        double med = sorted[sorted.size() / 2];

        // merge global top-k per query
        std::vector<Neighbor> merged(Q * K);
        for (std::size_t qi = 0; qi < Q; ++qi) {
            knn::KHeap heap(merged.data() + qi * K, K);
            for (int r = 0; r < size; ++r) {
                const Neighbor* part = gathered.data() + static_cast<std::size_t>(r) * Q * K + qi * K;
                for (std::size_t t = 0; t < K; ++t)
                    if (part[t].index >= 0) heap.push(part[t].index, part[t].dist2);
            }
            heap.finalize();
        }

        double qps = med > 0 ? (Q * 1000.0) / med : 0.0;
        std::printf("mpi size=%d n=%zu d=%zu q=%zu k=%zu reps=%zu\n", size, N, D, Q, K, reps);
        std::printf("median_compute_ms=%.3f qps=%.2f max_rss_kb=%ld rss_per_proc_kb=%ld\n",
                    med, qps, max_rss, rss_kb);

        if (!dump_path.empty()) {
            // dump idx (Q x K) int32 untuk verifikasi recall
            std::vector<std::int32_t> idx(Q * K);
            for (std::size_t i = 0; i < Q * K; ++i) idx[i] = merged[i].index;
            FILE* f = std::fopen(dump_path.c_str(), "wb");
            if (f) { std::fwrite(idx.data(), sizeof(std::int32_t), idx.size(), f); std::fclose(f); }
        }
    }

    MPI_Finalize();
    return 0;
}
