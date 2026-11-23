#!/usr/bin/env python3
"""run_bench_matrix.py — orkestrasi benchmark engine k-NN.

Menjalankan binary benchmark untuk beberapa konfigurasi (engine, mode, threads),
mem-parse ringkasan, menghitung speedup & parallel efficiency terhadap baseline,
lalu menulis CSV mentah + tabel ringkas ke layar.

Contoh (uji K1/K6 OpenMP di N=100000):
  python scripts/run_bench_matrix.py --n 100000 --d 384 --q 1000 --k 10 \
     --threads 1 2 4 --reps 3 --mode batch
"""
import argparse
import csv
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_RE = re.compile(
    r"median_time_ms=(?P<median>[\d.]+)\s+qps=(?P<qps>[\d.]+)\s+"
    r"p50=(?P<p50>[\d.]+)\s+p95=(?P<p95>[\d.]+)\s+p99=(?P<p99>[\d.]+)\s+"
    r"recall_ok=(?P<recall>\d)"
)


def run_one(binary, basis, queries, n, d, q, k, engine, mode, reps, threads):
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)
    cmd = [
        binary, "--basis", basis, "--queries", queries,
        "--n", str(n), "--d", str(d), "--q", str(q), "--k", str(k),
        "--engine", engine, "--mode", mode, "--reps", str(reps),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise RuntimeError(f"bench gagal ({engine},{mode},t={threads}): {out.stderr.strip()}")
    m = SUMMARY_RE.search(out.stdout)
    if not m:
        raise RuntimeError(f"tidak bisa parse output: {out.stdout!r}")
    row = {"engine": engine, "mode": mode, "threads": threads, "reps": reps,
           "n": n, "d": d, "q": q, "k": k}
    row.update({key: float(val) for key, val in m.groupdict().items() if key != "recall"})
    row["recall_ok"] = int(m.group("recall"))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=os.path.join(ROOT, "engine", "build", "bench_openmp"))
    ap.add_argument("--basis", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--d", type=int, required=True)
    ap.add_argument("--q", type=int, default=1000)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mode", default="batch", choices=["batch", "single-query"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    # baseline (1 thread) sebagai acuan speedup
    base = run_one(args.binary, args.basis, args.queries, args.n, args.d, args.q,
                   args.k, "baseline", args.mode, args.reps, 1)

    rows = [base]
    for t in args.threads:
        rows.append(run_one(args.binary, args.basis, args.queries, args.n, args.d,
                            args.q, args.k, "openmp", args.mode, args.reps, t))

    # acuan untuk efisiensi paralel: OpenMP 1 thread (kode optimasi yang sama)
    omp1 = next((r for r in rows if r["engine"] == "openmp" and r["threads"] == 1), None)

    print(f"\n== {args.mode} | N={args.n} D={args.d} Q={args.q} k={args.k} reps={args.reps} ==")
    print(f"{'engine':10} {'thr':>4} {'median_ms':>11} {'qps':>10} {'p95_ms':>9} "
          f"{'sp_vs_base':>11} {'sp_par':>7} {'par_eff%':>9} {'recall':>6}")
    print("-" * 86)
    for r in rows:
        sp_base = base["median"] / r["median"] if r["median"] > 0 else 0.0
        # speedup paralel diukur terhadap OpenMP 1 thread (isolasi efek paralelisasi)
        if omp1 and r["engine"] == "openmp" and r["median"] > 0:
            sp_par = omp1["median"] / r["median"]
        else:
            sp_par = 1.0
        eff = sp_par / r["threads"] * 100.0
        r["speedup_vs_base"] = sp_base
        r["speedup_par"] = sp_par
        r["parallel_eff_pct"] = eff
        print(f"{r['engine']:10} {r['threads']:>4} {r['median']:>11.3f} {r['qps']:>10.2f} "
              f"{r['p95']:>9.3f} {sp_base:>11.2f} {sp_par:>7.2f} {eff:>9.1f} {r['recall_ok']:>6}")

    print("\n  K1 (OpenMP 4thr vs baseline 1thr, >=2.5x) = "
          f"{next((r['speedup_vs_base'] for r in rows if r['engine']=='openmp' and r['threads']==max(args.threads)), 0):.2f}x")
    if omp1:
        r4 = next((r for r in rows if r["engine"] == "openmp" and r["threads"] == max(args.threads)), None)
        if r4:
            print(f"  K6 (parallel eff OpenMP {max(args.threads)}thr, >=62.5%) = {r4['parallel_eff_pct']:.1f}%")

    # tulis CSV
    out = args.out or os.path.join(ROOT, "results", "raw",
                                   f"bench_{args.mode}_N{args.n}_D{args.d}_{int(time.time())}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fields = ["engine", "mode", "threads", "n", "d", "q", "k", "reps",
              "median", "qps", "p50", "p95", "p99", "recall_ok",
              "speedup_vs_base", "speedup_par", "parallel_eff_pct"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
    print(f"\nCSV -> {out}")


if __name__ == "__main__":
    main()
