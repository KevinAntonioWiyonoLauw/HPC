"""llm.py — klien LLM OpenAI-compatible generik + fallback extractive lokal.

Provider bisa diubah runtime (base_url / api_key / model) lewat endpoint /config.
Mendukung GET /v1/models untuk "Fetch Models" di UI. Menangani 429 (rate limit)
dengan melaporkan retry-after; bila provider gagal, otomatis fallback ke
jawaban extractive dari konteks retrieval agar demo tetap berjalan offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import httpx


class LLMError(Exception):
    def __init__(self, message: str, status: Optional[int] = None,
                 retry_after_s: Optional[float] = None):
        super().__init__(message)
        self.status = status
        self.retry_after_s = retry_after_s


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 60.0
    max_tokens: int = 512


def _norm_base(base_url: str) -> str:
    b = base_url.rstrip("/")
    if b.endswith("/v1"):
        return b
    return b + "/v1"


def list_models(cfg: LLMConfig) -> List[str]:
    """GET {base}/v1/models -> daftar id model."""
    url = _norm_base(cfg.base_url) + "/models"
    headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
    try:
        r = httpx.get(url, headers=headers, timeout=cfg.timeout_s)
    except httpx.HTTPError as e:
        raise LLMError(f"gagal koneksi ke provider: {e}")
    if r.status_code != 200:
        raise LLMError(f"/models HTTP {r.status_code}: {r.text[:200]}", r.status_code)
    data = r.json()
    items = data.get("data", data if isinstance(data, list) else [])
    return [it.get("id") for it in items if isinstance(it, dict) and it.get("id")]


def chat(cfg: LLMConfig, system: str, user: str) -> str:
    """POST {base}/v1/chat/completions -> teks jawaban."""
    url = _norm_base(cfg.base_url) + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": cfg.max_tokens,
        "temperature": 0.2,
    }
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=cfg.timeout_s)
    except httpx.HTTPError as e:
        raise LLMError(f"gagal koneksi ke provider: {e}")
    if r.status_code == 429:
        retry = None
        try:
            retry = r.json().get("error", {}).get("details", {}).get("retryAfterMs", 0) / 1000.0
        except Exception:
            retry = None
        raise LLMError("rate limit (429) pada provider", 429, retry)
    if r.status_code != 200:
        raise LLMError(f"chat/completions HTTP {r.status_code}: {r.text[:300]}", r.status_code)
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(f"respons tidak terduga: {str(data)[:300]}")


def extractive_answer(question: str, passages: List[str]) -> str:
    """Fallback lokal: rangkai jawaban dari pasal hasil retrieval (tanpa LLM)."""
    if not passages:
        return ("Tidak ada pasal relevan yang ditemukan pada basis dokumen untuk "
                "pertanyaan ini.")
    head = passages[0].strip().replace("\n", " ")
    if len(head) > 400:
        head = head[:400] + "…"
    lines = [
        f"Berdasarkan dokumen kepatuhan yang paling relevan, jawaban untuk "
        f"\"{question.strip()}\" mengacu pada ketentuan berikut:",
        "",
        f"“{head}”",
        "",
        f"(Ringkasan extractive dari {len(passages)} pasal teratas; LLM eksternal "
        f"tidak aktif — fallback lokal.)",
    ]
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "Anda adalah asisten kepatuhan internal (SIKA). Jawab pertanyaan pengguna "
    "HANYA berdasarkan kutipan pasal yang diberikan. Sertakan rujukan nomor pasal. "
    "Jika informasi tidak ada pada konteks, katakan tidak ditemukan. Jawab ringkas "
    "dalam bahasa Indonesia."
)


def build_user_prompt(question: str, contexts: List[dict]) -> str:
    blocks = []
    for i, c in enumerate(contexts, 1):
        meta = c.get("meta", {})
        src = meta.get("sop", "DOKUMEN")
        pasal = meta.get("pasal", "")
        blocks.append(f"[{i}] {src} {pasal}\n{c.get('text', '').strip()}")
    ctx = "\n\n".join(blocks)
    return (
        f"Konteks pasal:\n{ctx}\n\n"
        f"Pertanyaan: {question}\n\n"
        f"Jawab berdasarkan konteks di atas dan sebutkan nomor pasal sumbernya."
    )
