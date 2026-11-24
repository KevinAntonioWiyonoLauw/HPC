"""config.py — konfigurasi service (env + path)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


class Config:
    # LLM (OpenAI-compatible) — bisa di-override runtime lewat POST /config
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:12800/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "tokenharbor/qwen3.8-flash")
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "60"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))

    # Embedding
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embed_device: str = os.getenv("EMBED_DEVICE", "cpu")

    # Path
    data_dir: Path = (ROOT / os.getenv("DATA_DIR", "data")).resolve()
    embeddings_dir: Path = data_dir / "embeddings"
    state_dir: Path = (ROOT / os.getenv("STATE_DIR", "state")).resolve()
    # Folder berkas dokumen yang diunggah pengguna (teks pasal/regulasi).
    docs_dir: Path = (ROOT / os.getenv("DOCS_DIR", "data/jdih_md")).resolve()

    # Mode muat basis: "preload" (baca penuh ke RAM) atau "mmap" (petakan berkas).
    load_mode: str = os.getenv("SIKA_LOAD_MODE", "preload").lower()

    # Batas konkurensi. 0 = tanpa batas. Untuk GPU sebaiknya 1 (serial per device).
    max_concurrency: int = int(os.getenv("SIKA_MAX_CONCURRENCY", "1"))
    max_embed_concurrency: int = int(os.getenv("SIKA_MAX_EMBED_CONCURRENCY", "4"))

    # Warmup saat startup. "full" (default) = embedding + semua engine; "engine"
    # = hanya engine (lewati embedding warmup, percepat start); "none" = lewati.
    warmup: str = os.getenv("SIKA_WARMUP", "full").lower()

    # MPI (engine opsional). Adapter menjalankan mpi_bench sebagai subprocess.
    mpi_procs: int = int(os.getenv("SIKA_MPI_PROCS", "4"))
    mpi_bin: str = os.getenv(
        "SIKA_MPI_BIN", str(ROOT / "engine" / "build" / "mpi_bench"))

    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))


config = Config()
