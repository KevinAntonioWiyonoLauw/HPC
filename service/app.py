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
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json
import os
import re

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

# Nilai awal dari .env, dipakai untuk reset.
_ENV_DEFAULTS = {
    "base_url": config.llm_base_url,
    "api_key": config.llm_api_key,
    "model": config.llm_model,
    "max_tokens": config.llm_max_tokens,
    "timeout_s": config.llm_timeout_s,
}
_STATE_FILE = config.state_dir / "llm.json"


def _load_state():
    """Muat override konfigurasi LLM dari berkas bila ada (persist antar restart)."""
    if not _STATE_FILE.exists():
        return
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("base_url", "api_key", "model", "max_tokens", "timeout_s"):
            if key in data and data[key] not in (None, ""):
                setattr(_llm_cfg, key, data[key])
        print(f"[startup] konfigurasi LLM dimuat dari {_STATE_FILE}")
    except Exception as e:  # pragma: no cover
        print(f"[startup] gagal memuat konfigurasi LLM: {e}")


def _save_state():
    """Simpan konfigurasi LLM saat ini ke berkas (API key tidak dicetak ke log)."""
    try:
        config.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "base_url": _llm_cfg.base_url,
                "api_key": _llm_cfg.api_key,
                "model": _llm_cfg.model,
                "max_tokens": _llm_cfg.max_tokens,
                "timeout_s": _llm_cfg.timeout_s,
            }, f, indent=2)
        os.replace(tmp, _STATE_FILE)
    except Exception as e:  # pragma: no cover
        print(f"[config] gagal menyimpan konfigurasi LLM: {e}")


# ----------------------------- cache (issue #12) -----------------------------
from collections import OrderedDict
import threading

_EMBED_CACHE: "OrderedDict[str, np.ndarray]" = OrderedDict()
_RETR_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_EMBED_CAP = 256
_RETR_CAP = 512


def _corpus_tag() -> str:
    return f"{manager.source}:{manager.n}:{manager.dim}"


def _cache_get(cache, key):
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    return None


def _cache_put(cache, key, val, cap):
    cache[key] = val
    cache.move_to_end(key)
    while len(cache) > cap:
        cache.popitem(last=False)


def embed_cached(text: str) -> np.ndarray:
    """Embedding satu teks dengan cache LRU."""
    v = _cache_get(_EMBED_CACHE, text)
    if v is None:
        v = embed_locked([text])
        _cache_put(_EMBED_CACHE, text, v, _EMBED_CAP)
    return v


def search_cached(text: str, k: int, engine: str):
    """Retrieval untuk teks kueri dengan cache LRU. Return (idx, dist, cached, ms)."""
    key = (text, k, engine, _corpus_tag())
    hit = _cache_get(_RETR_CACHE, key)
    if hit is not None:
        return hit[0], hit[1], True, 0.0
    q = embed_cached(text)
    idx, dist, ms = search_locked(q, k, engine)
    _cache_put(_RETR_CACHE, key, (idx, dist), _RETR_CAP)
    return idx, dist, False, ms


# --------------------------- konkurensi (issue #14) ---------------------------
# Engine GPU dipakai bersama; memanggilnya serentak justru membuat ekor latensi
# membengkak. Semaphore membatasi akses engine (default 1 = serial per device)
# dan embedding (default 4). Waktu tunggu serta panjang antrean dicatat agar
# angka p95/p99 jujur.

class _Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.queue_depth = 0
        self.max_queue_depth = 0
        self.total_waits = 0
        self.total_wait_ms = 0.0

    def enter(self):
        with self._lock:
            self.queue_depth += 1
            self.max_queue_depth = max(self.max_queue_depth, self.queue_depth)
            self.total_waits += 1
            return time.perf_counter()

    def leave(self, t0):
        with self._lock:
            self.queue_depth -= 1
            self.total_wait_ms += (time.perf_counter() - t0) * 1000.0

    def snapshot(self):
        with self._lock:
            avg = self.total_wait_ms / self.total_waits if self.total_waits else 0.0
            return {
                "queue_depth": self.queue_depth,
                "max_queue_depth": self.max_queue_depth,
                "total_waits": self.total_waits,
                "avg_wait_ms": round(avg, 3),
            }


_ENGINE_METRICS = _Metrics()
_EMBED_METRICS = _Metrics()
_ENGINE_SEM = threading.BoundedSemaphore(config.max_concurrency) if config.max_concurrency > 0 else None
_EMBED_SEM = threading.BoundedSemaphore(config.max_embed_concurrency) if config.max_embed_concurrency > 0 else None


def embed_locked(texts):
    """Encode embedding dengan batas konkurensi (bila diaktifkan)."""
    if _EMBED_SEM is None:
        return _embedder.encode(texts)
    t0 = _EMBED_METRICS.enter()
    with _EMBED_SEM:
        _EMBED_METRICS.leave(t0)
        return _embedder.encode(texts)


def search_locked(q, k, engine):
    """manager.search dengan batas konkurensi engine. Return (idx, dist, ms)."""
    if _ENGINE_SEM is None:
        return manager.search(q, k, engine)
    t0 = _ENGINE_METRICS.enter()
    with _ENGINE_SEM:
        _ENGINE_METRICS.leave(t0)
        return manager.search(q, k, engine)


@app.get("/queue/stats")
def queue_stats():
    return {
        "engine": _ENGINE_METRICS.snapshot(),
        "embed": _EMBED_METRICS.snapshot(),
        "engine_limit": config.max_concurrency,
        "embed_limit": config.max_embed_concurrency,
    }


@app.on_event("startup")
def _startup():
    _load_state()
    manager.load()
    t_start = time.perf_counter()
    mode = config.warmup
    # Warmup embedding agar request pertama tidak menanggung biaya muat model.
    # Lewati dengan SIKA_WARMUP=engine/none untuk mempercepat siklus evaluasi.
    if mode == "full":
        try:
            t0 = time.perf_counter()
            _embedder.encode(["warmup"])
            print(f"[startup] embedding warmup {time.perf_counter()-t0:.2f}s, dim={_embedder.dim}")
        except Exception as e:  # pragma: no cover
            print(f"[startup] embedding warmup gagal: {e}")
    else:
        print(f"[startup] embedding warmup dilewati (SIKA_WARMUP={mode})")
    # Warmup semua engine (terutama CUDA: inisialisasi context + H2D basis sekali).
    if mode in ("full", "engine"):
        try:
            dummy = np.zeros((1, manager.dim), dtype=np.float32)
            for eng in manager.engines():
                if eng == "mpi":
                    continue  # adapter subprocess; jangan spawn saat startup
                manager.search(dummy, 5, eng)
            print(f"[startup] engine warmup selesai untuk {manager.engines()}")
        except Exception as e:  # pragma: no cover
            print(f"[startup] engine warmup gagal: {e}")
    print(f"[startup] total warmup {time.perf_counter()-t_start:.2f}s (mode={mode})")


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
    reps: int = 3        # jumlah ulangan terukur (median dipakai)
    warmup: int = 20     # iterasi pemanasan (tidak diukur)


class CompareReq(BaseModel):
    query: str
    k: int = 10
    n: int = 100
    reps: int = 3
    warmup: int = 20
    engines: Optional[list] = None


class ConfigReq(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    timeout_s: Optional[float] = None


class DocUploadReq(BaseModel):
    name: str
    content: str
    title: Optional[str] = None
    year: Optional[str] = None
    unit: Optional[str] = None


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
    return embed_locked([req.query])


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


# ---------------- retrieval sadar nama dokumen ----------------
# Kueri seperti "isi dari TUGAS-P2_....md" menyebut nama berkas, bukan isi pasal.
# Embedding nama berkas tidak mirip dengan teks pasal, jadi kNN tidak akan
# menemukannya. Bila nama dokumen disebut eksplisit dan ada di korpus, ambil
# langsung seluruh potongan dokumen itu (urut per chunk).
_DOCNAME_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*\.md)\b", re.IGNORECASE)
_doc_index_cache = {"tag": None, "map": {}}


def _doc_index():
    """Peta doc_id -> daftar indeks item korpus (cache per tag korpus)."""
    tag = _corpus_tag()
    if _doc_index_cache["tag"] == tag:
        return _doc_index_cache["map"]
    mapping = {}
    c = manager.corpus
    if c is not None:
        for i, it in enumerate(c.items):
            did = (it.get("meta") or {}).get("doc_id")
            if did:
                mapping.setdefault(did, []).append(i)
    _doc_index_cache["tag"] = tag
    _doc_index_cache["map"] = mapping
    return mapping


def _doc_from_query(query: Optional[str]) -> Optional[str]:
    """Nama dokumen (tanpa .md) yang disebut eksplisit dan ada di korpus."""
    if not query:
        return None
    idx = _doc_index()
    for m in _DOCNAME_RE.finditer(query):
        stem = os.path.splitext(os.path.basename(m.group(1)))[0]
        if stem in idx:
            return stem
    return None


def _doc_hits(query: str, k: int):
    """(idx_row, dist_row, doc_id) untuk dokumen yang disebut namanya, atau None.

    Jarak tetap dihitung nyata (kuadrat Euclidean ke vektor kueri) supaya angka
    yang tampil di UI bukan angka karangan.
    """
    stem = _doc_from_query(query)
    if stem is None:
        return None
    items = manager.corpus.items if manager.corpus else []
    sel = sorted(
        _doc_index()[stem],
        key=lambda i: (((items[i].get("meta") or {}).get("chunk") or 0), i),
    )[: max(k, 1)]
    dists = []
    try:
        q = embed_cached(query)[0]
        mat = manager.corpus.matrix
        for i in sel:
            if mat is not None:
                diff = mat[i] - q
                dists.append(float(np.dot(diff, diff)))
            else:
                dists.append(0.0)
    except Exception:
        dists = [0.0] * len(sel)
    return (np.asarray([sel], dtype=np.int64),
            np.asarray([dists], dtype=np.float32), stem)


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
        "load_mode": config.load_mode,
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
    # Jalur vektor langsung (tanpa cache); jalur teks memakai cache LRU.
    if req.vector is None and req.query:
        eng = req.engine or manager.active
        direct = _doc_hits(req.query, req.k)
        if direct is not None:
            idx, dist, doc = direct
            return {
                "engine": eng,
                "k": req.k,
                "retrieval_ms": 0.0,
                "cached": False,
                "match": "document",
                "doc": doc,
                "results": _neighbors_to_dicts(idx[0], dist[0], manager.corpus, req.k),
            }
        idx, dist, cached, ms = search_cached(req.query, req.k, eng)
        return {
            "engine": eng,
            "k": req.k,
            "retrieval_ms": 0.0 if cached else round(ms, 3),
            "cached": cached,
            "match": "semantic",
            "results": _neighbors_to_dicts(idx[0], dist[0], manager.corpus, req.k),
        }
    q = _encode_query(req)
    if q.shape[1] != manager.dim:
        raise HTTPException(400, f"dimensi query {q.shape[1]} != basis {manager.dim}")
    idx, dist, ms = search_locked(q, req.k, req.engine)
    return {
        "engine": req.engine or manager.active,
        "k": req.k,
        "retrieval_ms": round(ms, 3),
        "cached": False,
        "results": _neighbors_to_dicts(idx[0], dist[0], manager.corpus, req.k),
    }


@app.post("/cache/clear")
def cache_clear():
    _EMBED_CACHE.clear()
    _RETR_CACHE.clear()
    return {"ok": True, "embed_entries": 0, "retr_entries": 0}


@app.get("/cache/stats")
def cache_stats():
    return {"embed_entries": len(_EMBED_CACHE), "retr_entries": len(_RETR_CACHE),
            "embed_cap": _EMBED_CAP, "retr_cap": _RETR_CAP}


@app.post("/ask")
def ask(req: AskReq):
    t0 = time.perf_counter()
    # Bila kueri menyebut nama dokumen, ambil potongan dokumen itu langsung;
    # kalau tidak, pakai kNN semantik dengan cache LRU.
    direct = _doc_hits(req.query, max(req.k, 12))
    if direct is not None:
        idx, dist, doc = direct
        cached, retr_ms, match = False, 0.0, "document"
    else:
        idx, dist, cached, retr_ms = search_cached(req.query, req.k, manager.active)
        doc, match = None, "semantic"
    # Embedding kini dilakukan di dalam search_cached; waktunya tercakup di total_ms.
    embed_ms = 0.0
    n_take = idx.shape[1] if direct is not None else req.k
    neigh = _neighbors_to_dicts(idx[0], dist[0], manager.corpus, n_take)

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
        "cached": cached,
        "latency": {
            "embed_ms": round(embed_ms, 3),
            "retrieval_ms": round(retr_ms, 3),
            "llm_ms": round(llm_ms, 3),
            "total_ms": round(total_ms, 3),
        },
        "llm_status": llm_status,
        "match": match,
        "doc": doc,
    }


@app.post("/ask/stream")
def ask_stream(req: AskReq):
    """SSE: kirim kutipan dulu, lalu token jawaban bertahap. Jalur non-stream tetap ada."""
    from fastapi.responses import StreamingResponse

    def gen():
        t0 = time.perf_counter()
        direct = _doc_hits(req.query, max(req.k, 12))
        if direct is not None:
            idx, dist, doc = direct
            cached, retr_ms, match = False, 0.0, "document"
            n_take = idx.shape[1]
        else:
            idx, dist, cached, retr_ms = search_cached(req.query, req.k, manager.active)
            doc, match, n_take = None, "semantic", req.k
        neigh = _neighbors_to_dicts(idx[0], dist[0], manager.corpus, n_take)
        meta = {
            "type": "citations", "engine": manager.active, "cached": cached,
            "retrieval_ms": round(retr_ms, 3), "citations": neigh,
            "match": match, "doc": doc,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        if not req.use_llm:
            yield f"data: {json.dumps({'type': 'done', 'llm_status': 'disabled'})}\n\n"
            return

        contexts = [{"text": n["text"], "meta": n["meta"]} for n in neigh]
        passages = [n["text"] for n in neigh]
        user_prompt = llm.build_user_prompt(req.query, contexts)
        tl = time.perf_counter()
        produced = False
        try:
            for delta in llm.chat_stream(_llm_cfg, llm.SYSTEM_PROMPT, user_prompt):
                produced = True
                yield f"data: {json.dumps({'type': 'delta', 'text': delta}, ensure_ascii=False)}\n\n"
            status = "ok" if produced else "ok-empty"
        except llm.LLMError as e:
            if not produced:
                fb = llm.extractive_answer(req.query, passages)
                yield f"data: {json.dumps({'type': 'delta', 'text': fb}, ensure_ascii=False)}\n\n"
            status = f"fallback: {e}"
        llm_ms = (time.perf_counter() - tl) * 1000.0
        total_ms = (time.perf_counter() - t0) * 1000.0
        yield f"data: {json.dumps({'type': 'done', 'llm_status': status, 'llm_ms': round(llm_ms, 3), 'total_ms': round(total_ms, 3)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _bench_engine(q, k: int, engine: Optional[str], n: int, reps: int, warmup: int):
    """Ukur satu engine dengan pemanasan + beberapa ulangan; median lintasan dipakai.

    Tiap ulangan menjalankan n pencarian dan mencatat latensi per-query. Statistik
    diambil dari gabungan sampel pada ulangan yang menghasilkan QPS median agar
    tahan terhadap outlier satu kali jalan (mis. GC, throttle sesaat).
    """
    for _ in range(max(0, warmup)):
        search_locked(q, k, engine)

    runs = []
    for _ in range(max(1, reps)):
        samples = []
        t0 = time.perf_counter()
        for _ in range(n):
            _, _, ms = search_locked(q, k, engine)
            samples.append(ms)
        wall = (time.perf_counter() - t0) * 1000.0
        qps = (n * 1000.0 / wall) if wall > 0 else 0.0
        runs.append((qps, np.array(samples, dtype=np.float64)))

    qps_runs = np.array([r[0] for r in runs], dtype=np.float64)
    med_qps = float(np.median(qps_runs))
    # pilih lintasan dengan QPS terdekat ke median sebagai representasi
    best = min(runs, key=lambda r: abs(r[0] - med_qps))
    arr = best[1]
    qps_mean = float(qps_runs.mean())
    qps_std = float(qps_runs.std(ddof=0))
    return {
        "engine": engine or manager.active,
        "n": n,
        "k": k,
        "reps": max(1, reps),
        "warmup": max(0, warmup),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
        "mean_ms": round(float(arr.mean()), 3),
        "std_ms": round(float(arr.std(ddof=0)), 3),
        "qps": round(med_qps, 2),
        "qps_mean": round(qps_mean, 2),
        "qps_std": round(qps_std, 2),
        "qps_cov": round(qps_std / qps_mean, 4) if qps_mean > 0 else 0.0,
        "qps_runs": [round(float(x), 2) for x in qps_runs],
    }


@app.post("/bench")
def bench(req: BenchReq):
    q = embed_locked([req.query])
    return _bench_engine(q, req.k, req.engine, req.n, req.reps, req.warmup)


@app.post("/bench/compare")
def bench_compare(req: CompareReq):
    """Benchmark semua engine secara adil: embedding sekali, tiap engine dapat
    pemanasan + ulangan yang sama, lalu diurutkan. Jauh lebih stabil daripada
    memanggil /bench terpisah-pisah dari klien."""
    q = embed_locked([req.query])
    names = req.engines or manager.engines()
    results = []
    for name in names:
        try:
            results.append(_bench_engine(q, req.k, name, req.n, req.reps, req.warmup))
        except Exception as e:  # lewati engine yang gagal
            results.append({"engine": name, "error": str(e)})
    return {"query": req.query, "k": req.k, "results": results}


@app.get("/models")
def models():
    try:
        ids = llm.list_models(_llm_cfg)
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
    return {"models": ids, "current": _llm_cfg.model}


# --------------------------- dokumen (manajemen berkas) ---------------------------
_DOC_SLUG = re.compile(r"[^a-zA-Z0-9._-]+")
_reindex_state = {"running": False, "last": None}


def _doc_path(name: str):
    """Resolusi aman nama berkas di dalam docs_dir (cegah path traversal)."""
    safe = os.path.basename(name)
    if not safe or safe != name or safe.startswith("."):
        raise HTTPException(400, "nama berkas tidak valid")
    return config.docs_dir / safe


def _norm_text(s: str) -> str:
    """Normalisasi teks unggahan: buang BOM/NUL/karakter kontrol, rapikan spasi."""
    s = (s or "").replace("\ufeff", "").replace("\u00a0", " ")
    s = "".join(ch if (ch in "\n\t" or ord(ch) >= 32) else " " for ch in s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.replace("\r\n", "\n").strip()


def _doc_summary(p):
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = ""
    pasal = len(re.findall(r"(?m)^##\s+Pasal", text))
    # ambil judul dari baris header "# KODE | Judul | Tahun | Unit"
    title = p.stem
    for line in text.splitlines():
        if line.startswith("# "):
            parts = [x.strip() for x in line[2:].split("|")]
            if len(parts) >= 2 and parts[1]:
                title = parts[1]
            break
    chunks = len(_doc_index().get(p.stem) or [])
    return {
        "name": p.name,
        "title": title,
        "pasal": pasal,
        "size": p.stat().st_size,
        "modified": int(p.stat().st_mtime),
        # Status nyata: apakah dokumen ini punya vektor di korpus yang sedang dilayani.
        "indexed": chunks > 0,
        "chunks": chunks,
    }


def _corpus_n() -> int:
    try:
        return int(manager.n)
    except Exception:
        return 0


def _count_real_items() -> int:
    """Hitung item non-filler (dokumen + SOP) tanpa melakukan embedding."""
    try:
        import importlib.util
        path = os.path.join(os.path.dirname(config.data_dir), "scripts", "build_corpus.py")
        spec = importlib.util.spec_from_file_location("_sika_build_corpus", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        docs = []
        if config.docs_dir.is_dir():
            docs += mod.load_markdown_docs(config.docs_dir)
        sop_dir = config.data_dir / "sop_synthetic"
        if sop_dir.is_dir():
            docs += mod.load_markdown_docs(sop_dir)
        return len(mod.build_items(docs))
    except Exception:
        return 0


def _reindex_filler() -> int:
    """Jumlah filler untuk reindex.

    Default "auto": jaga skala korpus (N) agar angka benchmark lama tetap
    sebanding. Dokumen baru mengisi slot filler, bukan menambah N.
    SIKA_REINDEX_FILLER=<angka> memaksa nilai tertentu.
    """
    env = (os.environ.get("SIKA_REINDEX_FILLER") or "").strip()
    if env and env.lower() != "auto":
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return max(0, _corpus_n() - _count_real_items())


def _start_reindex(background) -> dict:
    """Jalankan build_corpus di latar belakang. Idempoten bila sudah berjalan."""
    if _reindex_state["running"]:
        return {"ok": True, "started": False, "reason": "reindex sedang berjalan"}
    filler = _reindex_filler()

    def _run():
        _reindex_state["running"] = True
        try:
            import subprocess
            import sys as _sys
            script = os.path.join(os.path.dirname(config.data_dir), "scripts", "build_corpus.py")
            env = dict(os.environ)
            env["DOCS_DIR"] = str(config.docs_dir)
            r = subprocess.run(
                [_sys.executable, script, "--real-dir", str(config.docs_dir),
                 "--filler", str(filler)],
                capture_output=True, text=True, env=env, timeout=3600,
            )
            _reindex_state["last"] = {
                "ok": r.returncode == 0,
                "tail": (r.stdout or r.stderr)[-800:],
                "at": int(time.time()),
                "filler": filler,
            }
            if r.returncode == 0:
                # Korpus berubah: cache lama dan indeks dokumen tidak valid lagi.
                _EMBED_CACHE.clear()
                _RETR_CACHE.clear()
                _doc_index_cache["tag"] = None
                _doc_index_cache["map"] = {}
                manager._loaded = False
                manager.load()
        except Exception as e:  # pragma: no cover
            _reindex_state["last"] = {"ok": False, "tail": str(e), "at": int(time.time())}
        finally:
            _reindex_state["running"] = False

    background.add_task(_run)
    return {"ok": True, "started": True, "filler": filler}


@app.get("/documents")
def documents_list():
    d = config.docs_dir
    d.mkdir(parents=True, exist_ok=True)
    files = sorted(d.glob("*.md"), key=lambda p: p.name.lower())
    return {"dir": str(d), "count": len(files), "documents": [_doc_summary(p) for p in files]}


@app.post("/documents")
def documents_upload(req: "DocUploadReq", background: "BackgroundTasks"):
    config.docs_dir.mkdir(parents=True, exist_ok=True)
    raw_name = (req.name or "").strip() or "dokumen.md"
    stem = os.path.splitext(os.path.basename(raw_name))[0]
    stem = _DOC_SLUG.sub("-", stem).strip("-.") or "dokumen"
    # Jika konten belum berformat markdown pasal, bungkus dengan header + pasal.
    content = _norm_text(req.content)
    if not content.lstrip().startswith("#"):
        title = _norm_text(req.title or "") or stem.replace("-", " ").title()
        header = f"# {stem.upper()} | {title} | {req.year or ''} | {req.unit or 'Unit Referensi'}"
        if "## Pasal" in content or re.search(r"(?m)^Pasal\s+\d", content):
            # konversi baris "Pasal N" menjadi heading markdown
            body = re.sub(r"(?m)^\s*Pasal\s+(\d+[A-Za-z]?)\s*\.?\s*$", r"## Pasal \1", content)
        else:
            body = "## Pasal 1\n" + content
        content = header + "\n" + body + "\n"
    path = config.docs_dir / f"{stem}.md"
    path.write_text(content, encoding="utf-8")
    # Berkas tersimpan belum punya vektor: indeks ulang agar langsung bisa dicari.
    started = _start_reindex(background)
    return {"ok": True, "document": _doc_summary(path), "reindex": started}


@app.delete("/documents/{name}")
def documents_delete(name: str, background: "BackgroundTasks"):
    p = _doc_path(name)
    if not p.exists():
        raise HTTPException(404, "berkas tidak ditemukan")
    p.unlink()
    # Vektor dokumen yang dihapus harus hilang dari korpus.
    started = _start_reindex(background)
    return {"ok": True, "deleted": name, "reindex": started}


@app.post("/documents/reindex")
def documents_reindex(background: "BackgroundTasks"):
    """Bangun ulang korpus (embedding) dari berkas dokumen + SOP, latar belakang."""
    return _start_reindex(background)


@app.get("/documents/reindex/status")
def documents_reindex_status():
    return {"running": _reindex_state["running"], "last": _reindex_state["last"]}


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
    _save_state()
    return get_config()


@app.post("/config/reset")
def reset_config():
    """Kembalikan konfigurasi LLM ke nilai .env dan hapus berkas state."""
    for key, val in _ENV_DEFAULTS.items():
        setattr(_llm_cfg, key, val)
    try:
        if _STATE_FILE.exists():
            _STATE_FILE.unlink()
    except Exception:
        pass
    return get_config()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=config.api_host, port=config.api_port, reload=False)
