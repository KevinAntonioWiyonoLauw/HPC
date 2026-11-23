#!/usr/bin/env python3
"""evaluate_all.py — jalankan seluruh pengukuran & rangkum status K1–K7.

Mengasumsikan dataset sintetis sudah dibuat (atau membuatnya). Menjalankan:
  - baseline & openmp (batch + single-query) via bench_openmp
  - cuda (bila binary tersedia) via bench_cuda
  - mpi via mpirun (bila tersedia)
lalu mencetak tabel status kriteria kelulusan (Tabel 4.2).
"""
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "engine", "build")
SUMMARY_RE = re.compile(
    r"median_time_ms=(?P<median>[\d.]+)\s+qps=(?P<qps>[\d.]+)\s+"
    r"p50=(?P<p50>[\d.]+)\s+p95=(?P<p95>[\d.]+)\s+p99=(?P<p99>[\d.]+)\s+"
    r"recall_ok=(?P<recall>\d)"
)


def ensure_data(n, d, q):
    b = os.path.join(ROOT, "data", "out", f"basis_{n}_{d}.bin")
    qf = os.path.join(ROOT, "data", "out", f"queries_{q}_{d}.bin")
    if not (os.path.exists(b) and os.path.exists(qf)):
        subprocess.run([sys.executable, os.path.join(ROOT, "data", "gen_synthetic.py"),
                        "--n", str(n), "--d", str(d), "--q", str(q),
                        "--outdir", os.path.join(ROOT, "data", "out")], check=True)
    return b, qf


def run_bench(binary, basis, queries, n, d, q, k, engine, mode, reps, threads):
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(threads)
    env["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:" + env.get("LD_LIBRARY_PATH", "")
    cmd = [binary, "--basis", basis, "--queries", queries, "--n", str(n), "--d", str(d),
           "--q", str(q), "--k", str(k), "--engine", engine, "--mode", mode, "--reps", str(reps)]
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "bench gagal")
    m = SUMMARY_RE.search(out.stdout)
    return {kk: (int(v) if kk == "recall" else float(v)) for kk, v in m.groupdict().items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100000)
    ap.add_argument("--d", type=int, default=384)
    ap.add_argument("--q", type=int, default=1000)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mpi-n", type=int, default=500000, help="N untuk pengukuran K7 (jejak memori MPI)")
    ap.add_argument("--out-json", default=os.path.join(ROOT, "results", "report", "kpi_summary.json"))
    args = ap.parse_args()

    basis, queries = ensure_data(args.n, args.d, args.q)
    res = {}

    def have(path):
        return os.path.exists(path)

    openmp_bin = os.path.join(BUILD, "bench_openmp")
    cuda_bin = os.path.join(BUILD, "bench_cuda")
    mpi_bin = os.path.join(BUILD, "mpi_bench")

    print("== baseline batch (1 thread) ==")
    base_batch = run_bench(openmp_bin, basis, queries, args.n, args.d, args.q, args.k,
                           "baseline", "batch", args.reps, 1)
    res["baseline_batch"] = base_batch

    print("== openmp batch 4 thread ==")
    omp4 = run_bench(openmp_bin, basis, queries, args.n, args.d, args.q, args.k,
                     "openmp", "batch", args.reps, 4)
    res["openmp4_batch"] = omp4
    omp1 = run_bench(openmp_bin, basis, queries, args.n, args.d, args.q, args.k,
                     "openmp", "batch", args.reps, 1)
    res["openmp1_batch"] = omp1

    # baseline single-query (untuk p95 acuan)
    print("== baseline single-query ==")
    base_sq = run_bench(openmp_bin, basis, queries, args.n, args.d, args.q, args.k,
                        "baseline", "single-query", 1, 1)
    res["baseline_single"] = base_sq

    # CUDA
    if have(cuda_bin):
        print("== cuda batch ==")
        try:
            res["cuda_batch"] = run_bench(cuda_bin, basis, queries, args.n, args.d, args.q,
                                          args.k, "cuda", "batch", args.reps, 1)
            print("== cuda single-query ==")
            res["cuda_single"] = run_bench(cuda_bin, basis, queries, args.n, args.d, args.q,
                                           args.k, "cuda", "single-query", 1, 1)
        except Exception as e:
            print("cuda gagal:", e)
            res["cuda_error"] = str(e)

    # MPI memori (P=1 vs P=4) — pakai N lebih besar untuk memperjelas shard
    if have(mpi_bin):
        print(f"== mpi memory (P=1 & P=4) @ N={args.mpi_n} ==")
        mb, mq = ensure_data(args.mpi_n, args.d, 100)
        def run_mpi(P):
            cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(P), mpi_bin,
                   "--basis", mb, "--queries", mq, "--n", str(args.mpi_n), "--d", str(args.d),
                   "--q", "100", "--k", str(args.k), "--reps", "1"]
            out = subprocess.run(cmd, capture_output=True, text=True)
            m = re.search(r"median_compute_ms=([\d.]+).*rss_per_proc_kb=(\d+)", out.stdout)
            if not m:
                raise RuntimeError(out.stdout + out.stderr)
            return {"ms": float(m.group(1)), "rss_kb": int(m.group(2))}
        try:
            p1 = run_mpi(1); p4 = run_mpi(4)
            res["mpi_p1"] = p1; res["mpi_p4"] = p4
        except Exception as e:
            print("mpi gagal:", e)
            res["mpi_error"] = str(e)

    # ---------- evaluasi kriteria ----------
    kpi = {}
    kpi["K1_speedup_openmp4_vs_base"] = round(base_batch["median"] / omp4["median"], 2) if omp4["median"] else None
    kpi["K1_pass"] = kpi["K1_speedup_openmp4_vs_base"] is not None and kpi["K1_speedup_openmp4_vs_base"] >= 2.5
    if "cuda_batch" in res:
        kpi["K2_speedup_cuda_vs_base"] = round(base_batch["median"] / res["cuda_batch"]["median"], 2)
        kpi["K2_pass"] = kpi["K2_speedup_cuda_vs_base"] >= 20.0
    if "cuda_single" in res:
        kpi["K3_cuda_p95_ms"] = res["cuda_single"]["p95"]
        kpi["K3_pass"] = res["cuda_single"]["p95"] <= 100.0
    sp_par = omp1["median"] / omp4["median"] if omp4["median"] else None
    kpi["K6_parallel_eff_pct"] = round(sp_par / 4 * 100, 1) if sp_par else None
    kpi["K6_pass"] = kpi["K6_parallel_eff_pct"] is not None and kpi["K6_parallel_eff_pct"] >= 62.5
    # K5 recall: semua engine harus recall_ok=1
    recalls = [v.get("recall") for kk, v in res.items() if isinstance(v, dict) and "recall" in v]
    kpi["K5_recall_all_100"] = all(r == 1 for r in recalls) if recalls else None
    kpi["K5_pass"] = bool(kpi["K5_recall_all_100"])
    if "mpi_p1" in res and "mpi_p4" in res:
        kpi["K7_mem_reduction_x"] = round(res["mpi_p1"]["rss_kb"] / res["mpi_p4"]["rss_kb"], 2)
        kpi["K7_pass"] = kpi["K7_mem_reduction_x"] >= 3.0

    print("\n===== RINGKASAN KPI =====")
    for kk, vv in kpi.items():
        print(f"  {kk:32} = {vv}")

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump({"config": vars(args), "raw": res, "kpi": kpi}, f, indent=2)
    print(f"\nJSON -> {args.out_json}")


if __name__ == "__main__":
    main()
