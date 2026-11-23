"""store.py — pemuatan korpus: matriks vektor + metadata pasal.

Format korpus (hasil scripts/build_corpus.py):
  data/embeddings/<corpus>.f32   matriks float32 N x D (row-major)
  data/embeddings/<corpus>.json  {dim, n, items:[{id,text,meta:{sop,pasal,tahun,unit}}]}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


class Corpus:
    def __init__(self, name: str, dim: int, n: int, items: List[dict],
                 matrix: np.ndarray):
        self.name = name
        self.dim = dim
        self.n = n
        self.items = items
        self.matrix = matrix  # (N x D) float32

    def meta(self, idx: int) -> dict:
        return self.items[idx].get("meta", {})

    def text(self, idx: int) -> str:
        return self.items[idx].get("text", "")


def load_corpus(embeddings_dir: Path, name: str = "sika") -> Optional[Corpus]:
    vec_path = embeddings_dir / f"{name}.f32"
    meta_path = embeddings_dir / f"{name}.json"
    if not vec_path.exists() or not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    dim = int(meta["dim"])
    n = int(meta["n"])
    items = meta["items"]
    matrix = np.fromfile(vec_path, dtype=np.float32)
    if matrix.size < n * dim:
        raise ValueError("ukuran matriks < n*dim")
    matrix = matrix[: n * dim].reshape(n, dim)
    return Corpus(name, dim, n, items, matrix)
