#!/usr/bin/env python3
"""gen_synthetic.py — pembangkit matriks vektor sintetis (seed tetap, float32).

Menghasilkan dua berkas .bin mentah (row-major, float32):
  basis_{n}_{d}.bin     -> N x D
  queries_{q}_{d}.bin   -> Q x D
Berdistribusi seragam [0,1), seed tetap agar reproducible antar-engine.
"""
import argparse
import json
import os

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True, help="jumlah vektor basis")
    ap.add_argument("--d", type=int, required=True, help="dimensi")
    ap.add_argument("--q", type=int, default=1000, help="jumlah query")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default="data/out")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    basis = rng.uniform(0.0, 1.0, size=(args.n, args.d)).astype(np.float32)
    queries = rng.uniform(0.0, 1.0, size=(args.q, args.d)).astype(np.float32)

    bpath = os.path.join(args.outdir, f"basis_{args.n}_{args.d}.bin")
    qpath = os.path.join(args.outdir, f"queries_{args.q}_{args.d}.bin")
    basis.tofile(bpath)
    queries.tofile(qpath)

    meta = {
        "n": args.n,
        "d": args.d,
        "q": args.q,
        "seed": args.seed,
        "dtype": "float32",
        "layout": "row-major",
        "basis_file": os.path.basename(bpath),
        "queries_file": os.path.basename(qpath),
    }
    with open(os.path.join(args.outdir, f"meta_{args.n}_{args.d}.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"OK basis={bpath} ({basis.nbytes/1e6:.1f} MB) queries={qpath}")


if __name__ == "__main__":
    main()
