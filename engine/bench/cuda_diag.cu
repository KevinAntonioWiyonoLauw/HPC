#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cstdio>
int main(){
    int nd=0; cudaGetDeviceCount(&nd); printf("devices=%d\n",nd);
    cudaError_t e=cudaSetDevice(0); printf("setDevice=%s\n",cudaGetErrorString(e));
    cublasHandle_t h; cublasStatus_t s=cublasCreate(&h);
    printf("cublasCreate status=%d (%s)\n",(int)s, s==CUBLAS_STATUS_SUCCESS?"OK":"FAIL");
    void* p=nullptr; cudaError_t m=cudaMalloc(&p, 200ull*1024*1024);
    printf("cudaMalloc 200MB=%s ptr=%p\n",cudaGetErrorString(m),p);
    if(p) cudaFree(p);
    if(s==CUBLAS_STATUS_SUCCESS) cublasDestroy(h);
    return 0;
}
