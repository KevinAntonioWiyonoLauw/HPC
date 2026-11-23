#!/usr/bin/env python3
"""recall_check.py — validasi K5: himpunan indeks top-k identik dengan baseline.

Input: dua file .bin berisi indeks int32 (Q x k), mis. hasil dump engine vs baseline.
Atau pakai --from-engines untuk menghitung langsung via modul sika_engine.

Contoh (via binding):
  python scripts/recall_check.py --from-engines --basis data/out/basis_100000_384.bin \
    --queries data/out/queries_1000_384.bin --n 100000 --d 384 --q 1000 --k 10 \
    --compare cuda
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_from_engines(args):
    sys.path.insert(0, os.path.join(ROOT, "service"))
    import sika_engine

    eng = sika_engine.SikaEngine()
    eng.load_basis_file(args.basis, args.n, args.d)
    q = np.fromfile(args.queries, dtype=np.float32)[: args.q * args.d].reshape(args.q, args.d)

    ib, _ = eng.search("baseline", q, args.k)
    ib = np.asarray(ib)
    ok = True
    for name in args.compare:
        ic, _ = eng.search(name, q, args.k)
        ic = np.asarray(ic)
        same = np.all(np.sort(ib, axis=1) == np.sort(ic, axis=1))
        ok = ok and same
        print(f"recall {name:8} vs baseline: {'IDENTIK' if same else 'BEDA'} (K5 {'PASS' if same else 'FAIL'})")
    return 0 if ok else 1


def check_from_files(a, b, q, k):
    ia = np.fromfile(a, dtype=np.int32).reshape(q, k)
    ib = np.fromfile(b, dtype=np.int32).reshape(q, k)
    same = np.all(np.sort(ia, axis=1) == np.sort(ib, axis=1))
    print(f"recall: {'IDENTIK' if same else 'BEDA'} (K5 {'PASS' if same else 'FAIL'})")
    return 0 if same else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-engines", action="store_true")
    ap.add_argument("--basis")
    ap.add_argument("--queries")
    ap.add_argument("--n", type=int)
    ap.add_argument("--d", type=int)
    ap.add_argument("--q", type=int, default=1000)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--compare", nargs="+", default=["openmp"])
    ap.add_argument("--a")
    ap.add_argument("--b")
    args = ap.parse_args()
    if args.from_engines:
        sys.exit(check_from_engines(args))
    elif args.a and args.b:
        sys.exit(check_from_files(args.a, args.b, args.q, args.k))
    else:
        ap.error("pakai --from-engines atau --a/--b")


if __name__ == "__main__":
    main()
