#!/usr/bin/env python3
"""test_contract.py - uji kontrak KnnSearchFn untuk semua engine.

Memeriksa:
  1. Himpunan top-k tiap engine identik dengan baseline (recall 100%).
  2. Setiap engine mengembalikan Q x k hasil untuk batch.
  3. CUDA mengembalikan error (bukan hasil salah) untuk k yang tidak didukung (> 64).

Pemakaian:
  python scripts/test_contract.py --basis data/out/basis_5000_384.bin --n 5000 --d 384
Bila basis tidak ada, dibuat otomatis memakai data/gen_synthetic.py.
"""
import argparse
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "service"))


def ensure_basis(path, n, d):
    if os.path.exists(path):
        return
    outdir = os.path.dirname(path)
    subprocess.run([sys.executable, os.path.join(ROOT, "data", "gen_synthetic.py"),
                    "--n", str(n), "--d", str(d), "--q", "100", "--outdir", outdir], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", default=os.path.join(ROOT, "data", "out", "basis_5000_384.bin"))
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--d", type=int, default=384)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    ensure_basis(args.basis, args.n, args.d)

    import sika_engine

    eng = sika_engine.SikaEngine()
    eng.load_basis_file(args.basis, args.n, args.d)
    engines = eng.engines()
    print("engine tersedia:", engines)

    rng = np.random.default_rng(7)
    q = rng.uniform(0, 1, size=(40, args.d)).astype(np.float32)

    fails = 0
    ib, _ = eng.search("baseline", q, args.k)
    ib = np.asarray(ib)
    assert ib.shape == (40, args.k), f"shape baseline salah: {ib.shape}"

    for name in engines:
        idx, _ = eng.search(name, q, args.k)
        idx = np.asarray(idx)
        if idx.shape != (40, args.k):
            print(f"FAIL {name}: shape {idx.shape}")
            fails += 1
            continue
        same = np.array_equal(np.sort(ib, axis=1), np.sort(idx, axis=1))
        print(f"{'OK  ' if same else 'FAIL'} {name}: recall identik baseline = {same}")
        if not same:
            fails += 1

    # k di luar batas CUDA harus mengembalikan error, bukan hasil salah
    if "cuda" in engines:
        try:
            eng.search("cuda", q, 200)
            print("FAIL cuda: k=200 seharusnya error, tetapi mengembalikan hasil")
            fails += 1
        except Exception as e:
            print(f"OK   cuda: k=200 menolak dengan error ({type(e).__name__})")

    print()
    if fails == 0:
        print("KONTRAK LULUS untuk semua engine")
        sys.exit(0)
    print(f"{fails} pemeriksaan gagal")
    sys.exit(1)


if __name__ == "__main__":
    main()
