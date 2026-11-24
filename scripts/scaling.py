#!/usr/bin/env python3
"""scaling.py - analisis strong & weak scaling untuk OpenMP dan MPI.

Strong scaling : N tetap (default 250.000), tambah unit kerja (thread OpenMP /
                 proses MPI) di {1,2,4}; laporkan speedup S(P)=T1/TP dan
                 efisiensi E(P)=S(P)/P.
Weak scaling   : beban per unit tetap (default 150.000 vektor); P unit -> N=P*150k.
                 Laporkan efisiensi weak Ew(P)=T1/TP (ideal ~1).

Hasil: tabel di stdout + results/report/scaling.json + CSV siap pgfplots.

Contoh:
  python scripts/scaling.py --d 384 --q 200 --reps 3 --strong-n 250000 --weak-unit 150000
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "engine", "build")
SUMMARY_RE = re.compile(r"median_time_ms=([\d.]+)")
MPI_RE = re.compile(r"median_compute_ms=([\d.]+)")


def ensure_data(n, d, q, data_dir=None):
    data_dir = data_dir or os.path.join(ROOT, "data", "out")
    os.makedirs(data_dir, exist_ok=True)
    b = os.path.join(data_dir, f"basis_{n}_{d}.bin")
    qf = os.path.join(data_dir, f"queries_{q}_{d}.bin")
    if not (os.path.exists(b) and os.path.exists(qf)):
        subprocess.run([sys.executable, os.path.join(ROOT, "data", "gen_synthetic.py"),
                        "--n", str(n), "--d", str(d), "--q", str(q),
                        "--outdir", data_dir], check=True)
    return b, qf


def run_openmp(basis, queries, n, d, q, k, reps, threads):
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(threads)
    env["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:" + env.get("LD_LIBRARY_PATH", "")
    cmd = [os.path.join(BUILD, "bench_openmp"), "--basis", basis, "--queries", queries,
           "--n", str(n), "--d", str(d), "--q", str(q), "--k", str(k),
           "--engine", "openmp", "--mode", "batch", "--reps", str(reps)]
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    m = SUMMARY_RE.search(out.stdout)
    if not m:
        raise RuntimeError(out.stdout + out.stderr)
    return float(m.group(1))


def run_mpi(basis, queries, n, d, q, k, reps, procs):
    cmd = ["mpirun", "--oversubscribe", "-np", str(procs), os.path.join(BUILD, "mpi_bench"),
           "--basis", basis, "--queries", queries, "--n", str(n), "--d", str(d),
           "--q", str(q), "--k", str(k), "--reps", str(reps)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    m = MPI_RE.search(out.stdout)
    if not m:
        raise RuntimeError(out.stdout + out.stderr)
    return float(m.group(1))


def strong(name, runner, basis, queries, n, d, q, k, reps, units):
    res = {}
    base_t = None
    print(f"\n== Strong scaling {name} (N={n}) ==")
    print(f"{'P':>3} {'T(ms)':>12} {'speedup':>9} {'eff%':>7}")
    for P in units:
        t = runner(basis, queries, n, d, q, k, reps, P)
        if base_t is None:
            base_t = t
        sp = base_t / t if t else 0
        eff = sp / P * 100
        res[P] = {"T_ms": round(t, 3), "speedup": round(sp, 3), "eff_pct": round(eff, 1)}
        print(f"{P:>3} {t:>12.3f} {sp:>9.3f} {eff:>7.1f}")
    return res


def weak(name, runner, d, q, k, reps, unit, units, data_dir=None):
    res = {}
    base_t = None
    print(f"\n== Weak scaling {name} (unit={unit} vektor) ==")
    print(f"{'P':>3} {'N':>9} {'T(ms)':>12} {'Ew':>7}")
    for P in units:
        n = unit * P
        basis, queries = ensure_data(n, d, q, data_dir)
        t = runner(basis, queries, n, d, q, k, reps, P)
        if base_t is None:
            base_t = t
        ew = base_t / t if t else 0
        res[P] = {"N": n, "T_ms": round(t, 3), "Ew": round(ew, 3)}
        print(f"{P:>3} {n:>9} {t:>12.3f} {ew:>7.3f}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d", type=int, default=384)
    ap.add_argument("--q", type=int, default=200)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--strong-n", type=int, default=250000)
    ap.add_argument("--weak-unit", type=int, default=150000)
    ap.add_argument("--units", default="1,2,4")
    ap.add_argument("--data-dir", default=os.environ.get("SIKA_DATA_OUT", os.path.join(ROOT, "data", "out")))
    ap.add_argument("--out-json", default=os.path.join(ROOT, "results", "report", "scaling.json"))
    args = ap.parse_args()
    units = [int(x) for x in args.units.split(",")]

    out = {"config": vars(args)}
    sb, sq = ensure_data(args.strong_n, args.d, args.q, args.data_dir)
    out["strong_openmp"] = strong("OpenMP", run_openmp, sb, sq, args.strong_n, args.d, args.q,
                                  args.k, args.reps, units)
    out["strong_mpi"] = strong("MPI", run_mpi, sb, sq, args.strong_n, args.d, args.q,
                               args.k, args.reps, units)
    out["weak_openmp"] = weak("OpenMP", run_openmp, args.d, args.q, args.k, args.reps,
                              args.weak_unit, units, args.data_dir)
    out["weak_mpi"] = weak("MPI", run_mpi, args.d, args.q, args.k, args.reps,
                           args.weak_unit, units, args.data_dir)

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(out, f, indent=2)
    print("\nJSON ->", args.out_json)

    # CSV siap pgfplots (strong + weak)
    csv = os.path.join(os.path.dirname(args.out_json), "scaling.csv")
    with open(csv, "w") as f:
        f.write("kind,engine,P,T_ms,speedup,eff_pct,ew\n")
        for eng in ("openmp", "mpi"):
            for P, v in out[f"strong_{eng}"].items():
                f.write(f"strong,{eng},{P},{v['T_ms']},{v['speedup']},{v['eff_pct']},\n")
            for P, v in out[f"weak_{eng}"].items():
                f.write(f"weak,{eng},{P},{v['T_ms']},,,{v['Ew']}\n")
    print("CSV ->", csv)


if __name__ == "__main__":
    main()
