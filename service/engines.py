"""engines.py — manajer engine retrieval (bungkus pybind SikaEngine).

- Memuat matriks basis sekali (dari korpus bila ada, jika tidak dari dataset
  sintetis) lalu melayani banyak query.
- Menyimpan engine aktif (baseline/openmp/cuda/mpi) yang bisa ditukar runtime.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sika_engine  # noqa: E402  (hasil build pybind)

from config import config  # noqa: E402
from store import Corpus, load_corpus, load_corpus_meta  # noqa: E402


def _mpi_available() -> bool:
    """MPI dianggap tersedia bila mpirun ada di PATH dan binary mpi_bench ada."""
    if shutil.which("mpirun") is None:
        return False
    return Path(config.mpi_bin).exists()


class EngineManager:
    def __init__(self):
        self.engine = sika_engine.SikaEngine()
        self.corpus: Optional[Corpus] = None
        self.active: str = "baseline"
        self.source: str = "none"  # "corpus" | "synthetic"
        self._loaded = False
        self.basis_path: Optional[str] = None  # untuk adapter MPI (butuh file .f32)
        self._mpi = False

    # ---- pemuatan basis ----
    def load(self):
        if self._loaded:
            return
        use_mmap = config.load_mode == "mmap"
        # Override untuk benchmark skala besar / K4: muat basis sintetis via env
        override = os.environ.get("SIKA_BASIS_FILE")
        if override and os.path.exists(override):
            n = int(os.environ.get("SIKA_N", "0"))
            d = int(os.environ.get("SIKA_D", "384"))
            if use_mmap:
                self.engine.load_basis_mmap(override, n, d)
            else:
                self.engine.load_basis_file(override, n, d)
            self.source = "synthetic-bench"
            self.corpus = None
            self.basis_path = override
            self._after_load()
            return

        if use_mmap:
            # Mode mmap: metadata saja, matriks dipetakan langsung dari berkas .f32.
            corpus = load_corpus_meta(config.embeddings_dir, os.environ.get("SIKA_CORPUS", "sika"))
            if corpus is not None:
                self.corpus = corpus
                self.engine.load_basis_mmap(str(corpus.vec_path), corpus.n, corpus.dim)
                self.source = "corpus"
                self.basis_path = str(corpus.vec_path)
            else:
                raise RuntimeError(
                    "Mode mmap membutuhkan korpus (.f32 + .json). Jalankan "
                    "scripts/build_corpus.py atau pakai SIKA_LOAD_MODE=preload."
                )
        else:
            corpus = load_corpus(config.embeddings_dir, os.environ.get("SIKA_CORPUS", "sika"))
            if corpus is not None:
                self.corpus = corpus
                self.engine.load_basis_array(corpus.matrix, corpus.n, corpus.dim)
                self.source = "corpus"
                self.basis_path = str(corpus.vec_path)
            else:
                # fallback: dataset sintetis kecil agar service tetap bisa jalan
                basis_path = config.data_dir / "out" / "basis_5000_384.bin"
                if not basis_path.exists():
                    raise RuntimeError(
                        "Tidak ada korpus maupun dataset sintetis. Jalankan "
                        "scripts/build_corpus.py atau data/gen_synthetic.py."
                    )
                self.engine.load_basis_file(str(basis_path), 5000, 384)
                self.source = "synthetic"
                self.basis_path = str(basis_path)
        self._after_load()

    def _after_load(self):
        # Tentukan ketersediaan MPI (adapter subprocess mpi_bench).
        self._mpi = _mpi_available() and bool(self.basis_path)
        # pilih engine aktif pertama yang tersedia
        avail = self.engines()
        if self.active not in avail and avail:
            self.active = avail[0]
        self._loaded = True

    # ---- info ----
    def engines(self) -> List[str]:
        names = list(self.engine.engines())
        if self._mpi and "mpi" not in names:
            names.append("mpi")
        return names

    @property
    def dim(self) -> int:
        return self.engine.d

    @property
    def n(self) -> int:
        return self.engine.n

    def set_active(self, name: str):
        if name not in self.engines():
            raise ValueError(f"engine tidak tersedia: {name}")
        self.active = name

    # ---- pencarian ----
    def search(self, queries: np.ndarray, k: int,
               engine: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray, float]:
        """Return (idx, dist2, elapsed_ms) untuk engine aktif/terpilih."""
        name = engine or self.active
        q = np.ascontiguousarray(queries, dtype=np.float32)
        if name == "mpi":
            return self._search_mpi(q, k)
        t0 = time.perf_counter()
        idx, dist = self.engine.search(name, q, k)
        dt = (time.perf_counter() - t0) * 1000.0
        return np.asarray(idx), np.asarray(dist), dt

    def _search_mpi(self, q: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray, float]:
        """Adapter MPI: jalankan mpi_bench sebagai subprocess, baca dump idx+dist2.

        Menjaga kontrak (Q x k, dist2 menaik) dan sifat exact (identik baseline).
        """
        Q, D = q.shape
        with tempfile.TemporaryDirectory() as td:
            qpath = os.path.join(td, "q.bin")
            ipath = os.path.join(td, "idx.bin")
            dpath = os.path.join(td, "dist.bin")
            q.astype(np.float32).tofile(qpath)
            cmd = [
                "mpirun", "--oversubscribe", "-np", str(config.mpi_procs),
                config.mpi_bin,
                "--basis", self.basis_path, "--queries", qpath,
                "--n", str(self.n), "--d", str(D), "--q", str(Q), "--k", str(k),
                "--reps", "1", "--dump", ipath, "--dump-dist", dpath,
            ]
            t0 = time.perf_counter()
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            dt = (time.perf_counter() - t0) * 1000.0
            if r.returncode != 0:
                raise RuntimeError(f"mpi_bench gagal: {r.stderr.strip()[:300]}")
            idx = np.fromfile(ipath, dtype=np.int32).reshape(Q, k)
            dist = np.fromfile(dpath, dtype=np.float32).reshape(Q, k)
        return idx, dist, dt


manager = EngineManager()
