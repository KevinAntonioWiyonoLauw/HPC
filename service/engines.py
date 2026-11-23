"""engines.py — manajer engine retrieval (bungkus pybind SikaEngine).

- Memuat matriks basis sekali (dari korpus bila ada, jika tidak dari dataset
  sintetis) lalu melayani banyak query.
- Menyimpan engine aktif (baseline/openmp/cuda/mpi) yang bisa ditukar runtime.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sika_engine  # noqa: E402  (hasil build pybind)

from config import config  # noqa: E402
from store import Corpus, load_corpus  # noqa: E402


class EngineManager:
    def __init__(self):
        self.engine = sika_engine.SikaEngine()
        self.corpus: Optional[Corpus] = None
        self.active: str = "baseline"
        self.source: str = "none"  # "corpus" | "synthetic"
        self._loaded = False

    # ---- pemuatan basis ----
    def load(self):
        if self._loaded:
            return
        # Override untuk benchmark skala besar / K4: muat basis sintetis via env
        override = os.environ.get("SIKA_BASIS_FILE")
        if override and os.path.exists(override):
            n = int(os.environ.get("SIKA_N", "0"))
            d = int(os.environ.get("SIKA_D", "384"))
            self.engine.load_basis_file(override, n, d)
            self.source = "synthetic-bench"
            self.corpus = None
            avail = self.engine.engines()
            if self.active not in avail and avail:
                self.active = avail[0]
            self._loaded = True
            return

        corpus = load_corpus(config.embeddings_dir, "sika")
        if corpus is not None:
            self.corpus = corpus
            self.engine.load_basis_array(corpus.matrix, corpus.n, corpus.dim)
            self.source = "corpus"
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
        # pilih engine aktif pertama yang tersedia
        avail = self.engine.engines()
        if self.active not in avail and avail:
            self.active = avail[0]
        self._loaded = True

    # ---- info ----
    def engines(self) -> List[str]:
        return self.engine.engines()

    @property
    def dim(self) -> int:
        return self.engine.d

    @property
    def n(self) -> int:
        return self.engine.n

    def set_active(self, name: str):
        if name not in self.engine.engines():
            raise ValueError(f"engine tidak tersedia: {name}")
        self.active = name

    # ---- pencarian ----
    def search(self, queries: np.ndarray, k: int,
               engine: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray, float]:
        """Return (idx, dist2, elapsed_ms) untuk engine aktif/terpilih."""
        name = engine or self.active
        q = np.ascontiguousarray(queries, dtype=np.float32)
        t0 = time.perf_counter()
        idx, dist = self.engine.search(name, q, k)
        dt = (time.perf_counter() - t0) * 1000.0
        return np.asarray(idx), np.asarray(dist), dt


manager = EngineManager()
