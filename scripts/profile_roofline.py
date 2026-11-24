#!/usr/bin/env python3
"""profile_roofline.py - fallback profiling kuantitatif tanpa PMU/Nsight.

Ketika perf/valgrind tidak tersedia dan ncu tanpa izin (ERR_NVGPUCTRPERM), bukti
bottleneck tetap bisa diukur dari waktu nyata:
  - FLOPs efektif dan GFLOPS tercapai (compute-bound?),
  - byte traffic teoretis dan effective bandwidth GB/s (memory-bound?),
  - rasio komunikasi/komputasi MPI (comm_frac) dari mpi_bench.

FLOP per query = N * D * 3 (sub, mul, add untuk d2 = sum((q-p)^2)).
Byte traffic minimum = (N*D + Q*D)*4 (basis + query dibaca sekali).
Byte traffic naive    = Q*N*D*4 (basis dibaca ulang tiap query; tanpa tiling).

Untuk GPU GTX 1650 dipakai puncak referensi: ~128 GB/s, ~2.98 TFLOPS FP32.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "engine", "build")
SUMMARY_RE = re.compile(r"median_time_ms=([\d.]+)")
MPI_RE = re.compile(r"median_compute_ms=([\d.]+).*?comm_ms=([\d.]+)\s+comm_frac=([\d.]+)", re.S)


def run_bench(binary, basis, queries, n, d, q, k, engine, threads):
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(threads)
    env["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:" + env.get("LD_LIBRARY_PATH", "")
    cmd = [binary, "--basis", basis, "--queries", queries, "--n", str(n), "--d", str(d),
           "--q", str(q), "--k", str(k), "--engine", engine, "--mode", "batch", "--reps", "3"]
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    m = SUMMARY_RE.search(out.stdout)
    if not m:
        raise RuntimeError(out.stdout + out.stderr)
    return float(m.group(1))


def metrics(ms, n, d, q):
    flops = float(q) * n * d * 3.0
    gflops = flops / (ms / 1000.0) / 1e9 if ms > 0 else 0.0
    naive_bytes = float(q) * n * d * 4.0
    min_bytes = (float(n) * d + float(q) * d) * 4.0
    bw_naive = naive_bytes / (ms / 1000.0) / 1e9 if ms > 0 else 0.0
    bw_min = min_bytes / (ms / 1000.0) / 1e9 if ms > 0 else 0.0
    return gflops, bw_naive, bw_min, naive_bytes / min_bytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--d", type=int, required=True)
    ap.add_argument("--q", type=int, required=True)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "profiling", "roofline.txt"))
    args = ap.parse_args()

    lines = []
    lines.append(f"ROOFLINE EFEKTIF (fallback) N={args.n} D={args.d} Q={args.q} k={args.k}")
    lines.append("GPU referensi GTX 1650: bandwidth ~128 GB/s, FP32 ~2.98 TFLOPS")
    lines.append("")
    hdr = f"{'engine':10} {'ms':>10} {'GFLOPS':>9} {'BW_naive GB/s':>14} {'BW_min GB/s':>12} {'traffic_x':>10}"
    lines.append(hdr)
    lines.append("-" * len(hdr))

    cases = [
        ("baseline", os.path.join(BUILD, "bench_openmp"), "baseline", 1),
        ("openmp4", os.path.join(BUILD, "bench_openmp"), "openmp", 4),
    ]
    if os.path.exists(os.path.join(BUILD, "bench_cuda")):
        cases.append(("cuda", os.path.join(BUILD, "bench_cuda"), "cuda", 1))

    for name, binary, engine, threads in cases:
        try:
            ms = run_bench(binary, args.basis, args.queries, args.n, args.d, args.q, args.k, engine, threads)
            gf, bwn, bwm, tx = metrics(ms, args.n, args.d, args.q)
            lines.append(f"{name:10} {ms:>10.3f} {gf:>9.2f} {bwn:>14.2f} {bwm:>12.2f} {tx:>10.1f}")
        except Exception as e:
            lines.append(f"{name:10} GAGAL: {e}")

    # MPI comm ratio (P=4)
    mpi = os.path.join(BUILD, "mpi_bench")
    if os.path.exists(mpi):
        cmd = ["mpirun", "--oversubscribe", "-np", "4", mpi, "--basis", args.basis,
               "--queries", args.queries, "--n", str(args.n), "--d", str(args.d),
               "--q", str(args.q), "--k", str(args.k), "--reps", "1"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        m = MPI_RE.search(out.stdout)
        lines.append("")
        if m:
            ms, comm_ms, frac = m.group(1), m.group(2), m.group(3)
            lines.append(f"MPI P=4: compute={ms} ms comm(Gather+barrier)={comm_ms} ms "
                         f"comm_frac={frac} ({float(frac)*100:.2f}% waktu di komunikasi)")
        else:
            lines.append("MPI: gagal parsing. stdout=" + out.stdout[-300:])

    lines.append("")
    lines.append("Interpretasi: traffic_x = berapa kali basis dibaca dibanding minimum.")
    lines.append("baseline tanpa tiling ~ Q kali; openmp dengan tiling ~ Q/QBLK kali.")
    lines.append("BW_min mendekati puncak hardware => memory-bound; GFLOPS rendah => compute underutilized.")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    text = "\n".join(lines)
    with open(args.out, "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
