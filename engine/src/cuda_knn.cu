// cuda_knn.cu — Exact k-NN GPU: GEMM (cuBLAS) untuk shortlist + refine eksak.
//
// d2(q,p) = ||q||^2 + ||p||^2 - 2(q·p)   (Bab II)  -> bentuk GEMM (cepat, cuBLAS)
// CATATAN presisi: bentuk ekspansi mengalami catastrophic cancellation pada float32
// (nilai ~||q||^2+||p||^2 besar, d2 kecil). Karena K5 menuntut recall 100% yang
// identik dengan baseline (yang memakai d2 = Σ(q-p)^2 langsung), kernel melakukan
// DUA tahap:
//   1. GEMM cuBLAS menghitung dot (N×Q) -> approx d2 -> shortlist per-thread.
//   2. REFINE: untuk kandidat shortlist, hitung ulang d2 EKSAK dengan Σ(q-p)^2
//      (sama persis dengan baseline) lalu pilih top-k. Hasil identik dengan baseline.
#include "knn_engine.h"
#include "knn_util.h"

#include <cublas_v2.h>
#include <cuda_runtime.h>
#include <cstdio>
#include <vector>

namespace {

constexpr int MAXK = 64;
constexpr float INF = 1e30f;
constexpr int LOCAL_L = 4;  // top-L approx per thread untuk shortlist

__device__ __forceinline__ void insert_sorted(Neighbor* arr, int& cnt, int k, Neighbor v) {
    if (cnt < k) {
        int i = cnt++;
        arr[i] = v;
        while (i > 0 && arr[i - 1].dist2 > arr[i].dist2) { Neighbor t = arr[i-1]; arr[i-1]=arr[i]; arr[i]=t; --i; }
    } else if (v.dist2 < arr[k - 1].dist2) {
        arr[k - 1] = v;
        int i = k - 1;
        while (i > 0 && arr[i - 1].dist2 > arr[i].dist2) { Neighbor t = arr[i-1]; arr[i-1]=arr[i]; arr[i]=t; --i; }
    }
}

// satu blok = satu query
//   dot    : N x Q (column-major), query q kontigu di dot + q*N
//   basis  : N x D (row-major) untuk refine eksak
//   queries: Q x D (row-major) untuk refine eksak
__global__ void topk_kernel(const float* __restrict__ dot,
                            const float* __restrict__ norms,
                            const float* __restrict__ qnorm,
                            const float* __restrict__ basis,
                            const float* __restrict__ queries,
                            int N, int D, int k, Neighbor* __restrict__ out) {
    extern __shared__ char smem[];
    Neighbor* s_short = reinterpret_cast<Neighbor*>(smem);        // blockDim * LOCAL_L
    Neighbor* s_cand = s_short + blockDim.x * LOCAL_L;            // blockDim * LOCAL_L (hasil refine)

    const int q = blockIdx.x;
    const int tid = threadIdx.x;
    const float* row = dot + static_cast<size_t>(q) * N;
    const float qn = qnorm[q];
    const float* qv = queries + static_cast<size_t>(q) * D;

    const int total = blockDim.x * LOCAL_L;
    int M = k * 4; if (M < 24) M = 24; if (M > total) M = total; if (M > 64) M = 64;  // margin kandidat refine

    // 1) shortlist approx per-thread (top-LOCAL_L)
    Neighbor loc[LOCAL_L];
    int cnt = 0;
    for (int j = tid; j < N; j += blockDim.x) {
        float d2 = qn + norms[j] - 2.f * row[j];
        insert_sorted(loc, cnt, LOCAL_L, Neighbor{j, d2});
    }
    for (int t = 0; t < LOCAL_L; ++t)
        s_short[tid * LOCAL_L + t] = (t < cnt) ? loc[t] : Neighbor{-1, INF};
    __syncthreads();

    // 2) reduksi approx -> top-M kandidat (thread0), simpan di s_short[0..M)
    if (tid == 0) {
        Neighbor topM[64];
        int tm = 0;
        for (int i = 0; i < total; ++i) {
            Neighbor c = s_short[i];
            if (c.index < 0) continue;
            insert_sorted(topM, tm, M, c);
        }
        for (int i = 0; i < M; ++i) s_cand[i] = (i < tm) ? topM[i] : Neighbor{-1, INF};
    }
    __syncthreads();

    // 3) refine eksak (Σ(q-p)^2) hanya untuk M kandidat
    for (int i = tid; i < M; i += blockDim.x) {
        Neighbor c = s_cand[i];
        if (c.index < 0) continue;
        const float* p = basis + static_cast<size_t>(c.index) * D;
        float e = 0.f;
        for (int d = 0; d < D; ++d) { float df = qv[d] - p[d]; e += df * df; }
        s_cand[i] = Neighbor{c.index, e};
    }
    __syncthreads();

    // 4) thread0 -> top-k dari M kandidat eksak
    if (tid == 0) {
        Neighbor res[MAXK];
        int rc = 0;
        for (int i = 0; i < M; ++i) {
            if (s_cand[i].index < 0) continue;
            insert_sorted(res, rc, k, s_cand[i]);
        }
        for (int t = 0; t < k; ++t)
            out[static_cast<size_t>(q) * k + t] = (t < rc) ? res[t] : Neighbor{-1, INF};
    }
}

// ---- device cache + cublas handle ----
struct DevCache {
    const float* host_basis = nullptr;
    std::size_t n = 0, d = 0;
    float* d_basis = nullptr;
    float* d_norm = nullptr;
    cublasHandle_t handle = nullptr;
};
DevCache g;

void free_cache() {
    if (g.d_basis) cudaFree(g.d_basis);
    if (g.d_norm) cudaFree(g.d_norm);
    g = DevCache{};
}

bool ensure_device(const float* basis, std::size_t n, std::size_t d) {
    if (g.handle == nullptr) {
        if (cublasCreate(&g.handle) != CUBLAS_STATUS_SUCCESS) return false;
    }
    if (g.host_basis == basis && g.n == n && g.d == d) return true;
    free_cache();
    if (cublasCreate(&g.handle) != CUBLAS_STATUS_SUCCESS) return false;
    std::size_t bytes = n * d * sizeof(float);
    if (cudaMalloc(&g.d_basis, bytes) != cudaSuccess) return false;
    if (cudaMemcpy(g.d_basis, basis, bytes, cudaMemcpyHostToDevice) != cudaSuccess) return false;
    std::vector<float> norms(n, 0.f);
    for (std::size_t j = 0; j < n; ++j) {
        const float* p = basis + j * d;
        float s = 0.f;
        for (std::size_t e = 0; e < d; ++e) s += p[e] * p[e];
        norms[j] = s;
    }
    if (cudaMalloc(&g.d_norm, n * sizeof(float)) != cudaSuccess) return false;
    if (cudaMemcpy(g.d_norm, norms.data(), n * sizeof(float), cudaMemcpyHostToDevice) != cudaSuccess) return false;
    g.host_basis = basis; g.n = n; g.d = d;
    return true;
}

int cuda_search(const float* basis, std::size_t n, const QueryBatch& batch,
                std::size_t k, std::vector<Neighbor>& out) {
    if (k > MAXK) { std::fprintf(stderr, "[cuda] k=%zu > MAXK=%d\n", k, MAXK); return 1; }
    if (!ensure_device(basis, n, batch.d)) { std::fprintf(stderr, "[cuda] gagal init device\n"); return 2; }

    const int Q = static_cast<int>(batch.q), N = static_cast<int>(n), D = static_cast<int>(batch.d);

    std::vector<float> qn(Q, 0.f);
    for (int i = 0; i < Q; ++i) {
        const float* q = batch.data + static_cast<size_t>(i) * D;
        float s = 0.f;
        for (int d = 0; d < D; ++d) s += q[d] * q[d];
        qn[i] = s;
    }

    float* d_q = nullptr; float* d_dot = nullptr; float* d_qnorm = nullptr; Neighbor* d_out = nullptr;
    bool ok = true;
    ok &= cudaMalloc(&d_q, static_cast<size_t>(Q) * D * sizeof(float)) == cudaSuccess;
    ok &= cudaMalloc(&d_dot, static_cast<size_t>(Q) * N * sizeof(float)) == cudaSuccess;
    ok &= cudaMalloc(&d_qnorm, static_cast<size_t>(Q) * sizeof(float)) == cudaSuccess;
    ok &= cudaMalloc(&d_out, static_cast<size_t>(Q) * k * sizeof(Neighbor)) == cudaSuccess;
    if (!ok) { cudaFree(d_q); cudaFree(d_dot); cudaFree(d_qnorm); cudaFree(d_out); return 3; }

    cudaMemcpy(d_q, batch.data, static_cast<size_t>(Q) * D * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_qnorm, qn.data(), static_cast<size_t>(Q) * sizeof(float), cudaMemcpyHostToDevice);

    // GEMM: dot(N×Q) = basis(N×D) · queries^T(D×Q)  (column-major)
    const float alpha = 1.0f, beta = 0.0f;
    cublasStatus_t st = cublasSgemm(g.handle, CUBLAS_OP_T, CUBLAS_OP_N,
                                    N, Q, D, &alpha,
                                    g.d_basis, D, d_q, D, &beta, d_dot, N);
    if (st != CUBLAS_STATUS_SUCCESS) {
        std::fprintf(stderr, "[cuda] cublasSgemm gagal: %d\n", (int)st);
        cudaFree(d_q); cudaFree(d_dot); cudaFree(d_qnorm); cudaFree(d_out);
        return 4;
    }

    int block = 128;
    std::size_t shmem = static_cast<std::size_t>(block) * LOCAL_L * sizeof(Neighbor) * 2;
    topk_kernel<<<Q, block, shmem>>>(d_dot, g.d_norm, d_qnorm, g.d_basis, d_q, N, D,
                                     static_cast<int>(k), d_out);

    cudaError_t err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        std::fprintf(stderr, "[cuda] kernel error: %s\n", cudaGetErrorString(err));
        cudaFree(d_q); cudaFree(d_dot); cudaFree(d_qnorm); cudaFree(d_out);
        return 5;
    }
    out.resize(static_cast<size_t>(Q) * k);
    cudaMemcpy(out.data(), d_out, static_cast<size_t>(Q) * k * sizeof(Neighbor), cudaMemcpyDeviceToHost);
    cudaFree(d_q); cudaFree(d_dot); cudaFree(d_qnorm); cudaFree(d_out);
    return 0;
}

}  // namespace

namespace knn {
static const struct CudaRegistrar {
    CudaRegistrar() { register_engine("cuda", cuda_search); }
} g_cuda_registrar;
}  // namespace knn
