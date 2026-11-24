// pybind_module.cpp — expose engine k-NN ke Python (SikaEngine)
//
// SikaEngine memuat matriks basis sekali (preload), lalu melayani banyak query
// lewat engine yang bisa ditukar (baseline/openmp/cuda/mpi) tanpa reload basis.
#include "knn_engine.h"
#include "knn_util.h"

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace py = pybind11;

class SikaEngine {
public:
    ~SikaEngine() { unmap(); }

    void load_basis_file(const std::string& path, std::size_t n, std::size_t d) {
        unmap();
        std::vector<float> data;
        if (!knn::load_bin_f32(path, data))
            throw std::runtime_error("gagal membaca file basis: " + path);
        if (data.size() < n * d)
            throw std::runtime_error("ukuran file < n*d");
        basis_.assign(data.begin(), data.begin() + n * d);
        n_ = n; d_ = d;
        mode_ = "preload";
    }

    void load_basis_array(py::array_t<float, py::array::c_style | py::array::forcecast> arr,
                          std::size_t n, std::size_t d) {
        unmap();
        auto buf = arr.request();
        const float* p = static_cast<const float*>(buf.ptr);
        basis_.assign(p, p + n * d);
        n_ = n; d_ = d;
        mode_ = "preload";
    }

    // Petakan berkas .f32 (N x D, row-major) langsung dengan mmap. Halaman dimuat
    // sesuai kebutuhan sehingga RAM tidak menahan seluruh matriks. Kontrak engine
    // tidak berubah: search tetap menerima pointer basis (N x D).
    void load_basis_mmap(const std::string& path, std::size_t n, std::size_t d) {
        unmap();
        int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error("gagal membuka file basis: " + path);
        struct stat st{};
        if (::fstat(fd, &st) != 0) { ::close(fd); throw std::runtime_error("fstat gagal"); }
        std::size_t need = n * d * sizeof(float);
        if (static_cast<std::size_t>(st.st_size) < need) {
            ::close(fd);
            throw std::runtime_error("ukuran file < n*d");
        }
        void* p = ::mmap(nullptr, need, PROT_READ, MAP_PRIVATE, fd, 0);
        ::close(fd);  // mapping tetap valid setelah fd ditutup
        if (p == MAP_FAILED) throw std::runtime_error("mmap gagal");
        mmap_ptr_ = p; mmap_bytes_ = need;
        n_ = n; d_ = d;
        mode_ = "mmap";
    }

    std::size_t n() const { return n_; }
    std::size_t d() const { return d_; }
    std::string load_mode() const { return mode_; }

    // queries: array (Q x D) float32; return (idx QxK int32, dist2 QxK float32)
    py::tuple search(const std::string& engine,
                     py::array_t<float, py::array::c_style | py::array::forcecast> queries,
                     std::size_t k) {
        const float* basis = base_ptr();
        if (basis == nullptr) throw std::runtime_error("basis belum dimuat");
        auto qbuf = queries.request();
        if (qbuf.ndim != 2) throw std::runtime_error("queries harus 2D (Q x D)");
        const std::size_t Q = static_cast<std::size_t>(qbuf.shape[0]);
        const std::size_t D = static_cast<std::size_t>(qbuf.shape[1]);
        if (D != d_) throw std::runtime_error("dimensi query != dimensi basis");

        KnnSearchFn fn = knn::find_engine(engine);
        if (!fn) throw std::runtime_error("engine tidak terdaftar: " + engine);

        QueryBatch batch{static_cast<const float*>(qbuf.ptr), Q, D};
        std::vector<Neighbor> out;
        int rc = fn(basis, n_, batch, k, out);
        if (rc != 0) throw std::runtime_error("engine mengembalikan error");

        py::array_t<std::int32_t> idx({static_cast<py::ssize_t>(Q), static_cast<py::ssize_t>(k)});
        py::array_t<float> dist({static_cast<py::ssize_t>(Q), static_cast<py::ssize_t>(k)});
        auto ib = idx.mutable_unchecked<2>();
        auto db = dist.mutable_unchecked<2>();
        for (std::size_t qi = 0; qi < Q; ++qi)
            for (std::size_t j = 0; j < k; ++j) {
                ib(static_cast<py::ssize_t>(qi), static_cast<py::ssize_t>(j)) = out[qi * k + j].index;
                db(static_cast<py::ssize_t>(qi), static_cast<py::ssize_t>(j)) = out[qi * k + j].dist2;
            }
        return py::make_tuple(idx, dist);
    }

    std::vector<std::string> engines() const { return knn::engine_names(); }

private:
    const float* base_ptr() const {
        if (mmap_ptr_ != nullptr) return static_cast<const float*>(mmap_ptr_);
        if (!basis_.empty()) return basis_.data();
        return nullptr;
    }

    void unmap() {
        if (mmap_ptr_ != nullptr) {
            ::munmap(mmap_ptr_, mmap_bytes_);
            mmap_ptr_ = nullptr;
            mmap_bytes_ = 0;
        }
    }

    std::vector<float> basis_;
    void* mmap_ptr_ = nullptr;
    std::size_t mmap_bytes_ = 0;
    std::size_t n_ = 0, d_ = 0;
    std::string mode_ = "none";
};

PYBIND11_MODULE(sika_engine, m) {
    m.doc() = "SIKA k-NN engine (pybind11)";
    py::class_<SikaEngine>(m, "SikaEngine")
        .def(py::init<>())
        .def("load_basis_file", &SikaEngine::load_basis_file, py::arg("path"),
             py::arg("n"), py::arg("d"))
        .def("load_basis_array", &SikaEngine::load_basis_array, py::arg("arr"),
             py::arg("n"), py::arg("d"))
        .def("load_basis_mmap", &SikaEngine::load_basis_mmap, py::arg("path"),
             py::arg("n"), py::arg("d"))
        .def("search", &SikaEngine::search, py::arg("engine"), py::arg("queries"),
             py::arg("k"))
        .def("engines", &SikaEngine::engines)
        .def_property_readonly("n", &SikaEngine::n)
        .def_property_readonly("d", &SikaEngine::d)
        .def_property_readonly("load_mode", &SikaEngine::load_mode);
}
