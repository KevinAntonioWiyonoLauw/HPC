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

    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))


config = Config()
