// knn_engine.h — Kontrak antarmuka engine retrieval (Listing V.1 proposal)
// Semua varian (baseline / openmp / cuda / mpi) mengimplementasikan typedef ini
// sehingga perbandingan performa setara secara antarmuka.
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

struct Neighbor {
    std::int32_t index;  // indeks baris pada basis vektor
    float        dist2;  // kuadrat jarak Euclidean
};

struct QueryBatch {
    const float* data;   // layout baris: Q x D, float32
    std::size_t  q;      // jumlah query
    std::size_t  d;      // dimensi
};

// basis : matriks N x D, row-major
// out   : Q x k, terurut menaik menurut dist2
// return: 0 sukses, non-nol gagal (mis. VRAM tidak cukup)
using KnnSearchFn = int (*)(const float* basis, std::size_t n,
                            const QueryBatch& batch, std::size_t k,
                            std::vector<Neighbor>& out);
