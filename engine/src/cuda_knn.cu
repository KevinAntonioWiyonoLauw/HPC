// cuda_knn.cu — Exact k-NN GPU: GEMM-form + shared memory + block reduction
//
// d2(q,p) = ||q||^2 + ||p||^2 - 2(q·p)   (lihat Bab II proposal)
// - Matriks basis dipindahkan H2D SEKALI (device cache), bukan per query.
// - Satu blok per query: query dimuat ke shared memory, tiap thread memindai
//   sebagian basis (registers), menjaga top-k lokal, lalu blok melakukan
//   reduksi top-k di shared memory -> hasil Q x k.
#include "knn_engine.h"
#include "knn_util.h"

#include <cuda_runtime.h>
#include <cstdio>
#include <limits>
#include <vector>

namespace {

constexpr int MAXK = 64;      // batas k yang didukung kernel
constexpr int BLOCK = 256;    // thread per blok (maks)

__device__ __forceinline__ void insert_sorted(Neighbor* arr, int& cnt, int k,
                                              Neighbor v) {
    if (cnt < k) {
        int i = cnt++;
        arr[i] = v;
        while (i > 0 && arr[i - 1].dist2 > arr[i].dist2) {
            Neighbor t = arr[i - 1]; arr[i - 1] = arr[i]; arr[i] = t; --i;
        }
    } else if (v.dist2 < arr[k - 1].dist2) {
        arr[k - 1] = v;
        int i = k - 1;
        while (i > 0 && arr[i - 1].dist2 > arr[i].dist2) {
            Neighbor t = arr[i - 1]; arr[i - 1] = arr[i]; arr[i] = t; --i;
        }
    }
}

__global__ void knn_kernel(const float* __restrict__ basis,
                           const float* __restrict__ norms,
                           const float* __restrict__ queries, int Q, int N, int D,
                           int k, Neighbor* __restrict__ out) {
    extern __shared__ char smem[];
    float* s_q = reinterpret_cast<float*>(smem);       // D float
    Neighbor* s_cand = reinterpret_cast<Neighbor*>(s_q + D);  // B*k
    float* s_red = reinterpret_cast<float*>(s_cand + blockDim.x * k);  // reduksi

    const int q = blockIdx.x;
    const int tid = threadIdx.x;
    const float* qptr = queries + static_cast<size_t>(q) * D;

    // muat query ke shared + hitung ||q||^2
    float qacc = 0.f;
    for (int d = tid; d < D; d += blockDim.x) {
        float v = qptr[d];
        s_q[d] = v;
        qacc += v * v;
    }
    s_red[tid] = qacc;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) s_red[tid] += s_red[tid + s];
        __syncthreads();
    }
    const float qnorm = s_red[0];
    __syncthreads();

    // top-k lokal per thread
    Neighbor local[MAXK];
    int cnt = 0;
    for (int j = tid; j < N; j += blockDim.x) {
        const float* p = basis + static_cast<size_t>(j) * D;
        float dot = 0.f;
#pragma unroll 4
        for (int d = 0; d < D; ++d) dot += s_q[d] * p[d];
        float d2 = qnorm + norms[j] - 2.f * dot;
        insert_sorted(local, cnt, k, Neighbor{j, d2});
    }

    // tulis kandidat ke shared (pad dengan inf)
    for (int t = 0; t < k; ++t)
        s_cand[tid * k + t] = (t < cnt) ? local[t]
                                        : Neighbor{-1, std::numeric_limits<float>::infinity()};
    __syncthreads();

    // reduksi: thread 0 gabungkan B*k kandidat -> top-k akhir
    if (tid == 0) {
        Neighbor res[MAXK];
        int rc = 0;
        const int total = blockDim.x * k;
        for (int i = 0; i < total; ++i) {
            Neighbor c = s_cand[i];
            if (c.index < 0) continue;
            insert_sorted(res, rc, k, c);
        }
        for (int t = 0; t < k; ++t)
            out[static_cast<size_t>(q) * k + t] =
                (t < rc) ? res[t] : Neighbor{-1, std::numeric_limits<float>::infinity()};
    }
}

// ---- device cache: basis + norms dipindah H2D sekali ----
struct DevCache {
    const float* host_basis = nullptr;
    std::size_t n = 0, d = 0;
    float* d_basis = nullptr;
    float* d_norm = nullptr;
};
DevCache g_cache;

void free_cache() {
    if (g_cache.d_basis) cudaFree(g_cache.d_basis);
    if (g_cache.d_norm) cudaFree(g_cache.d_norm);
    g_cache = DevCache{};
}

bool ensure_device(const float* basis, std::size_t n, std::size_t d) {
    if (g_cache.host_basis == basis && g_cache.n == n && g_cache.d == d)
        return true;  // cache hit -> tanpa H2D
    free_cache();
    std::size_t bytes = n * d * sizeof(float);
    if (cudaMalloc(&g_cache.d_basis, bytes) != cudaSuccess) return false;
    if (cudaMemcpy(g_cache.d_basis, basis, bytes, cudaMemcpyHostToDevice) != cudaSuccess)
        return false;
    // norms dihitung di host lalu di-copy (sekali)
    std::vector<float> norms(n, 0.f);
    for (std::size_t j = 0; j < n; ++j) {
        const float* p = basis + j * d;
        float s = 0.f;
        for (std::size_t e = 0; e < d; ++e) s += p[e] * p[e];
        norms[j] = s;
    }
    if (cudaMalloc(&g_cache.d_norm, n * sizeof(float)) != cudaSuccess) return false;
    if (cudaMemcpy(g_cache.d_norm, norms.data(), n * sizeof(float),
                   cudaMemcpyHostToDevice) != cudaSuccess)
        return false;
    g_cache.host_basis = basis; g_cache.n = n; g_cache.d = d;
    return true;
}

int cuda_search(const float* basis, std::size_t n, const QueryBatch& batch,
                std::size_t k, std::vector<Neighbor>& out) {
    if (k > MAXK) {
        std::fprintf(stderr, "[cuda] k=%zu melebihi MAXK=%d\n", k, MAXK);
        return 1;
    }
    if (!ensure_device(basis, n, batch.d)) {
        std::fprintf(stderr, "[cuda] gagal alokasi/pindah basis ke VRAM\n");
        return 2;
    }

    // pilih block size agar shared memory <= 48KB
    int block = BLOCK;
    while (block > 32 &&
           (static_cast<int>(batch.d) * 4 + block * static_cast<int>(k) * 8 +
            block * 4) > 48 * 1024)
        block -= 32;
    std::size_t shmem = batch.d * 4 + block * k * 8 + block * 4;

    float* d_q = nullptr;
    std::size_t qbytes = batch.q * batch.d * sizeof(float);
    if (cudaMalloc(&d_q, qbytes) != cudaSuccess) return 3;
    cudaMemcpy(d_q, batch.data, qbytes, cudaMemcpyHostToDevice);

    Neighbor* d_out = nullptr;
    std::size_t obytes = batch.q * k * sizeof(Neighbor);
    if (cudaMalloc(&d_out, obytes) != cudaSuccess) { cudaFree(d_q); return 3; }

    dim3 grid(static_cast<unsigned>(batch.q));
    dim3 blk(static_cast<unsigned>(block));
    knn_kernel<<<grid, blk, shmem>>>(g_cache.d_basis, g_cache.d_norm, d_q,
                                     static_cast<int>(batch.q), static_cast<int>(n),
                                     static_cast<int>(batch.d), static_cast<int>(k),
                                     d_out);
    cudaError_t err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        std::fprintf(stderr, "[cuda] kernel error: %s\n", cudaGetErrorString(err));
        cudaFree(d_q); cudaFree(d_out);
        return 4;
    }

    out.resize(batch.q * k);
    cudaMemcpy(out.data(), d_out, obytes, cudaMemcpyDeviceToHost);
    cudaFree(d_q);
    cudaFree(d_out);
    return 0;
}

}  // namespace

namespace knn {
static const struct CudaRegistrar {
    CudaRegistrar() { register_engine("cuda", cuda_search); }
} g_cuda_registrar;
}  // namespace knn
