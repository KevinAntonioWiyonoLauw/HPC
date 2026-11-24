#!/usr/bin/env python3
"""measure_k4.py - ukur K4 resmi: latensi p95 POST /search pada N=500.000.

Menyalakan service (uvicorn) dengan override basis besar (SIKA_BASIS_FILE),
menunggu /health, lalu mengirim banyak permintaan POST /search memakai `vector`
(melewati embedding -> retrieval murni), menghitung p50/p95/p99. Latensi dengan
embedding dilaporkan terpisah (memakai `query`) sesuai Subbab 4.2.

Hasil ditulis ke results/report/k4.json dan (opsional) digabung ke kpi_summary.json.

Contoh:
  python scripts/measure_k4.py --n 500000 --d 384 --requests 300 --engine auto
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _post(url, payload, timeout=120):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return (time.perf_counter() - t0) * 1000.0, body


def _get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def start_service(basis, n, d, port, load_mode):
    env = dict(os.environ)
    env["SIKA_BASIS_FILE"] = basis
    env["SIKA_N"] = str(n)
    env["SIKA_D"] = str(d)
    env["SIKA_WARMUP"] = "none"
    env["SIKA_LOAD_MODE"] = load_mode
    env["SIKA_MAX_CONCURRENCY"] = "0"  # tanpa antrean -> latensi per-request bersih
    env["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:" + env.get("LD_LIBRARY_PATH", "")
    env["STATE_DIR"] = "/tmp/sika_k4_state"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=os.path.join(ROOT, "service"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(600):
        try:
            _get(base + "/health", timeout=2)
            return proc, base
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("service tidak siap")


def pctl(a, p):
    return float(np.percentile(np.array(a, dtype=np.float64), p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500000)
    ap.add_argument("--d", type=int, default=384)
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--engine", default="auto", help="auto|cuda|openmp|baseline")
    ap.add_argument("--load-mode", default="preload")
    ap.add_argument("--basis", default=None)
    ap.add_argument("--queries", default=None)
    ap.add_argument("--out-json", default=os.path.join(ROOT, "results", "report", "k4.json"))
    ap.add_argument("--merge-kpi", default=os.path.join(ROOT, "results", "report", "kpi_summary.json"))
    args = ap.parse_args()

    basis = args.basis or os.path.join(ROOT, "data", "out", f"basis_{args.n}_{args.d}.bin")
    queries = args.queries or os.path.join(ROOT, "data", "out", f"queries_1000_{args.d}.bin")
    if not os.path.exists(basis):
        raise SystemExit(f"basis tidak ada: {basis}. Buat dulu data/gen_synthetic.py.")

    port = _free_port()
    print(f"menyalakan service di :{port} (N={args.n}, load_mode={args.load_mode}) ...")
    proc, base = start_service(basis, args.n, args.d, port, args.load_mode)
    try:
        engs = _get(base + "/engines")["engines"]
        engine = args.engine
        if engine == "auto":
            # Probe engine terbaik yang benar-benar jalan pada basis besar. CUDA
            # bisa gagal init bila VRAM tersisa kurang (GPU 4 GB dipakai bersama);
            # dalam hal itu fallback ke openmp. Batasan dicatat, N tidak diturunkan.
            probe_vec = np.fromfile(queries, dtype=np.float32)[:args.d].tolist()
            chosen = None
            for cand in ["cuda", "openmp", "baseline"]:
                if cand not in engs:
                    continue
                try:
                    _post(base + "/search", {"vector": probe_vec, "k": args.k, "engine": cand})
                    chosen = cand
                    break
                except Exception as e:
                    print(f"  engine {cand} gagal dipakai ({e}); coba berikutnya")
            engine = chosen or ("openmp" if "openmp" in engs else "baseline")
        print(f"engine terpilih: {engine} (tersedia: {engs})")

        qv = np.fromfile(queries, dtype=np.float32)
        d = args.d
        nq = min(args.requests, qv.size // d)
        vectors = [qv[i * d:(i + 1) * d].tolist() for i in range(nq)]

        # warmup
        for _ in range(10):
            _post(base + "/search", {"vector": vectors[0], "k": args.k, "engine": engine})

        # --- retrieval murni (tanpa embedding) ---
        retr = []
        for v in vectors:
            ms, _ = _post(base + "/search", {"vector": v, "k": args.k, "engine": engine})
            retr.append(ms)

        # --- dengan embedding (query teks) untuk memisahkan latensi embedding ---
        # Panaskan embedding dulu (model dimuat lazy saat warmup=none) agar angka
        # embedding tidak tercemar cold-start pemuatan model.
        _post(base + "/search", {"query": "warmup embedding", "k": args.k, "engine": engine})
        emb = []
        text = "uang harian perjalanan dinas luar kota nomor "
        for i in range(min(50, nq)):
            ms, _ = _post(base + "/search", {"query": text + str(i), "k": args.k, "engine": engine})
            emb.append(ms)

        k4 = {
            "config": {"n": args.n, "d": d, "k": args.k, "engine": engine,
                        "requests": nq, "load_mode": args.load_mode,
                        "engines_available": engs},
            "retrieval_only_ms": {"p50": round(pctl(retr, 50), 3), "p95": round(pctl(retr, 95), 3),
                                   "p99": round(pctl(retr, 99), 3), "mean": round(float(np.mean(retr)), 3)},
            "with_embedding_ms": {"p50": round(pctl(emb, 50), 3), "p95": round(pctl(emb, 95), 3),
                                   "p99": round(pctl(emb, 99), 3), "mean": round(float(np.mean(emb)), 3),
                                   "samples": len(emb)},
        }
        k4["K4_pass"] = k4["retrieval_only_ms"]["p95"] <= 100.0
        print("K4 retrieval p50/p95/p99 (ms):",
              k4["retrieval_only_ms"]["p50"], k4["retrieval_only_ms"]["p95"], k4["retrieval_only_ms"]["p99"])
        print("dengan embedding p95 (ms):", k4["with_embedding_ms"]["p95"])

        os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(k4, f, indent=2)
        print("JSON ->", args.out_json)

        # merge ke kpi_summary bila ada / buat baru
        if args.merge_kpi:
            summary = {}
            if os.path.exists(args.merge_kpi):
                with open(args.merge_kpi) as f:
                    summary = json.load(f)
            summary.setdefault("kpi", {})
            summary["kpi"]["K4_p95_ms"] = k4["retrieval_only_ms"]["p95"]
            summary["kpi"]["K4_pass"] = k4["K4_pass"]
            summary.setdefault("k4_detail", k4)
            os.makedirs(os.path.dirname(args.merge_kpi), exist_ok=True)
            with open(args.merge_kpi, "w") as f:
                json.dump(summary, f, indent=2)
            print("K4 digabung ke", args.merge_kpi)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
