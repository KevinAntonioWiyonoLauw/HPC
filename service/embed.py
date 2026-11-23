"""embed.py — embedding teks -> vektor float32 (all-MiniLM-L6-v2, CPU).

Model dimuat lazy saat pertama dipakai agar service bisa start cepat.
"""
from __future__ import annotations

from typing import List

import numpy as np


class Embedder:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dim = None

    def _ensure(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy import

            self._model = SentenceTransformer(self.model_name, device=self.device)
            getter = getattr(self._model, "get_embedding_dimension", None) or \
                self._model.get_sentence_embedding_dimension
            self._dim = int(getter())
        return self._model

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._ensure()
        return self._dim

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        model = self._ensure()
        vecs = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return np.ascontiguousarray(vecs, dtype=np.float32)
