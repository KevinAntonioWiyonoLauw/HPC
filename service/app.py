"""app.py — FastAPI service SIKA.

Endpoint:
  GET  /health            status ringkas
  GET  /status            info engine, korpus, konfigurasi LLM (api key disamarkan)
  GET  /engines           daftar engine + engine aktif
  POST /engine            tukar engine aktif {name}
  POST /search            retrieval saja {query|vector, k, engine?} -> top-k + latensi
  POST /ask               retrieval + LLM {query, k} -> jawaban + kutipan + breakdown
  POST /bench             jalankan retrieval n kali -> p50/p95/p99 + QPS (demo beban)
  GET  /models            daftar model provider (Fetch Models)
  GET  /config            konfigurasi LLM (api key disamarkan)
  POST /config            set konfigurasi LLM runtime
"""
from __future__ import annotations

import time
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import llm
from config import config
from embed import Embedder
from engines import manager

app = FastAPI(title="SIKA — Exact k-NN Retrieval (HPC)", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_embedder = Embedder(config.embed_model, config.embed_device)
_llm_cfg = llm.LLMConfig(
    base_url=config.llm_base_url, api_key=config.llm_api_key,
    model=config.llm_model, timeout_s=config.llm_timeout_s,
    max_tokens=config.llm_max_tokens,
)


@app.on_event("startup")
def _startup():
    manager.load()
    # Warmup embedding agar request pertama tidak menanggung biaya muat model.
    try:
        t0 = time.perf_counter()
        _embedder.encode(["warmup"])
        print(f"[startup] embedding warmup {time.perf_counter()-t0:.2f}s, dim={_embedder.dim}")
    except Exception as e:  # pragma: no cover
        print(f"[startup] embedding warmup gagal: {e}")


# ----------------------------- models -----------------------------
class SearchReq(BaseModel):
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    k: int = 10
    engine: Optional[str] = None


class AskReq(BaseModel):
    query: str
    k: int = 10
    use_llm: bool = True


class EngineReq(BaseModel):
    name: str


class BenchReq(BaseModel):
    query: str
    k: int = 10
    n: int = 100
    engine: Optional[str] = None


class ConfigReq(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    timeout_s: Optional[float] = None


# ----------------------------- helpers -----------------------------
def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "***"


def _encode_query(req: SearchReq) -> np.ndarray:
    if req.vector is not None:
        return np.asarray([req.vector], dtype=np.float32)
    if not req.query:
        raise HTTPException(400, "butuh 'query' atau 'vector'")
    return _embedder.encode([req.query])


def _neighbors_to_dicts(idx_row, dist_row, corpus, k):
    out = []
    for j in range(min(k, len(idx_row))):
        i = int(idx_row[j])
        d2 = float(dist_row[j])
        item = {
            "rank": j + 1,
            "index": i,
            "dist2": d2,
            "distance": float(np.sqrt(max(d2, 0.0))),
            "text": corpus.text(i) if corpus else "",
            "meta": corpus.meta(i) if corpus else {},
        }
        out.append(item)
    return out


# ----------------------------- routes -----------------------------
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    return {
        "engine_active": manager.active,
        "engines": manager.engines(),
        "source": manager.source,
        "n": manager.n,
        "dim": manager.dim,
        "corpus": manager.corpus.name if manager.corpus else None,
        "llm": {
            "base_url": _llm_cfg.base_url,
            "model": _llm_cfg.model,
            "api_key": _mask(_llm_cfg.api_key),
        },
    }


@app.get("/engines")
def engines():
    return {"engines": manager.engines(), "active": manager.active}


@app.post("/engine")
def set_engine(req: EngineReq):
    try:
        manager.set_active(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"active": manager.active}


@app.post("/search")
def search(req: SearchReq):
    q = _encode_query(req)
    if q.shape[1] != manager.dim:
        raise HTTPException(400, f"dimensi query {q.shape[1]} != basis {manager.dim}")
    idx, dist, ms = manager.search(q, req.k, req.engine)
    return {
        "engine": req.engine or manager.active,
        "k": req.k,
        "retrieval_ms": round(ms, 3),
        "results": _neighbors_to_dicts(idx[0], dist[0], manager.corpus, req.k),
    }


@app.post("/ask")
def ask(req: AskReq):
    t0 = time.perf_counter()
    q = _embedder.encode([req.query])
    embed_ms = (time.perf_counter() - t0) * 1000.0

    idx, dist, retr_ms = manager.search(q, req.k, None)
    neigh = _neighbors_to_dicts(idx[0], dist[0], manager.corpus, req.k)

    contexts = [{"text": n["text"], "meta": n["meta"]} for n in neigh]
    passages = [n["text"] for n in neigh]

    llm_ms = 0.0
    answer = None
    llm_status = "disabled"
    if req.use_llm:
        user_prompt = llm.build_user_prompt(req.query, contexts)
        tl = time.perf_counter()
        try:
            answer = llm.chat(_llm_cfg, llm.SYSTEM_PROMPT, user_prompt)
            llm_status = "ok"
        except llm.LLMError as e:
            answer = llm.extractive_answer(req.query, passages)
            llm_status = f"fallback: {e}"
        llm_ms = (time.perf_counter() - tl) * 1000.0

    total_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "query": req.query,
        "answer": answer,
        "citations": neigh,
        "engine": manager.active,
        "latency": {
            "embed_ms": round(embed_ms, 3),
            "retrieval_ms": round(retr_ms, 3),
            "llm_ms": round(llm_ms, 3),
            "total_ms": round(total_ms, 3),
        },
        "llm_status": llm_status,
    }


@app.post("/bench")
def bench(req: BenchReq):
    q = _embedder.encode([req.query])
    samples = []
    for _ in range(req.n):
        _, _, ms = manager.search(q, req.k, req.engine)
        samples.append(ms)
    arr = np.array(samples, dtype=np.float64)
    total = arr.sum()
    qps = (req.n * 1000.0 / total) if total > 0 else 0.0
    return {
        "engine": req.engine or manager.active,
        "n": req.n,
        "k": req.k,
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
        "mean_ms": round(float(arr.mean()), 3),
        "qps": round(qps, 2),
    }


@app.get("/models")
def models():
    try:
        ids = llm.list_models(_llm_cfg)
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
    return {"models": ids, "current": _llm_cfg.model}


@app.get("/config")
def get_config():
    return {
        "base_url": _llm_cfg.base_url,
        "model": _llm_cfg.model,
        "api_key": _mask(_llm_cfg.api_key),
        "max_tokens": _llm_cfg.max_tokens,
        "timeout_s": _llm_cfg.timeout_s,
    }


@app.post("/config")
def set_config(req: ConfigReq):
    if req.base_url is not None:
        _llm_cfg.base_url = req.base_url
    if req.api_key is not None:
        _llm_cfg.api_key = req.api_key
    if req.model is not None:
        _llm_cfg.model = req.model
    if req.max_tokens is not None:
        _llm_cfg.max_tokens = req.max_tokens
    if req.timeout_s is not None:
        _llm_cfg.timeout_s = req.timeout_s
    return get_config()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=config.api_host, port=config.api_port, reload=False)
