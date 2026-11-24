#!/usr/bin/env python3
"""ingest_jdih.py - impor regulasi publik nyata (JDIH) menjadi korpus SIKA.

Skrip ini TIDAK mengarang teks hukum. Ia mengubah berkas regulasi asli yang sudah
diunduh dari JDIH (mis. https://peraturan.go.id, JDIH kementerian/lembaga) menjadi
format markdown yang dibaca scripts/build_corpus.py, lalu korpus dibangun dengan
embedding MiniLM.

Format berkas masukan (.txt atau .md) di folder --src:
  Baris pertama (opsional, dipisah '|'):
      <kode SOP> | <judul> | <tahun> | <unit>
  Diikuti isi pasal, misalnya:
      Pasal 1
      Isi pasal ...
      Pasal 2
      Isi pasal ...

Contoh pemakaian:
  # 1) unduh regulasi JDIH sebagai .txt ke data/jdih_raw/ (satu berkas per aturan)
  # 2) konversi ke format markdown SOP
  python scripts/ingest_jdih.py --src data/jdih_raw --out data/sop_synthetic
  # 3) bangun korpus (embedding) lalu jalankan evaluasi/laporan seperti biasa
  python scripts/build_corpus.py --filler 20000

Tanpa berkas asli, skrip tetap bisa diuji dengan contoh kecil (lihat --self-test).
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASAL_RE = re.compile(r"^\s*Pasal\s+(\d+[A-Za-z]?)\b[.:]?\s*(.*)$", re.IGNORECASE)


def parse_regulation(text: str):
    """Kembalikan (header, list[(pasal, isi)])."""
    lines = text.splitlines()
    header = {"sop": "", "judul": "", "tahun": "", "unit": ""}
    body_start = 0
    if lines:
        first = lines[0].strip()
        if "|" in first:
            parts = [p.strip() for p in first.split("|")]
            header["sop"] = parts[0] if len(parts) > 0 else ""
            header["judul"] = parts[1] if len(parts) > 1 else ""
            header["tahun"] = parts[2] if len(parts) > 2 else ""
            header["unit"] = parts[3] if len(parts) > 3 else ""
            body_start = 1
    pasal = []
    cur_no, cur = None, []
    for line in lines[body_start:]:
        m = PASAL_RE.match(line)
        if m:
            if cur_no is not None:
                pasal.append((cur_no, " ".join(t.strip() for t in cur if t.strip())))
            cur_no = f"Pasal {m.group(1)}"
            cur = [m.group(2)] if m.group(2).strip() else []
        elif line.strip():
            if cur_no is None:
                cur_no = "Pasal 1"
            cur.append(line)
    if cur_no is not None:
        pasal.append((cur_no, " ".join(t.strip() for t in cur if t.strip())))
    return header, pasal


def to_markdown(header: dict, pasal: list, stem: str) -> str:
    sop = header.get("sop") or stem
    judul = header.get("judul") or stem
    tahun = header.get("tahun") or "0"
    unit = header.get("unit") or "Unit Referensi"
    out = [f"# {sop} | {judul} | {tahun} | {unit}"]
    for no, isi in pasal:
        out.append(f"## {no}")
        out.append(isi)
    return "\n".join(out) + "\n"


def ingest(src: Path, out: Path):
    files = sorted([p for p in src.glob("*") if p.suffix.lower() in (".txt", ".md")])
    if not files:
        print(f"Tidak ada berkas .txt/.md di {src}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for p in files:
        header, pasal = parse_regulation(p.read_text(encoding="utf-8"))
        if not pasal:
            print(f"Lewati {p.name}: tidak ada pasal terdeteksi")
            continue
        md = to_markdown(header, pasal, p.stem)
        (out / f"{p.stem}.md").write_text(md, encoding="utf-8")
        total += len(pasal)
        print(f"{p.name}: {len(pasal)} pasal -> {out / (p.stem + '.md')}")
    print(f"Total {total} pasal dari {len(files)} berkas.")
    return 0


def self_test():
    """Uji parser + konversi dengan contoh kecil (bukan teks hukum nyata)."""
    sample = (
        "SOP-UJI-01 | Contoh Aturan Uji | 2024 | Unit Uji\n"
        "Pasal 1\nIsi pasal pertama contoh.\n"
        "Pasal 2\nIsi pasal kedua contoh.\n"
        "Pasal 3A\nIsi pasal ketiga A.\n"
    )
    header, pasal = parse_regulation(sample)
    assert header["sop"] == "SOP-UJI-01", header
    assert len(pasal) == 3, pasal
    assert pasal[2][0] == "Pasal 3A", pasal
    md = to_markdown(header, pasal, "contoh")
    assert md.startswith("# SOP-UJI-01 | Contoh Aturan Uji | 2024 | Unit Uji")
    assert "## Pasal 2" in md
    print("SELF-TEST OK:", len(pasal), "pasal terparse")
    print(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data" / "jdih_raw"))
    ap.add_argument("--out", default=str(ROOT / "data" / "sop_synthetic"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    sys.exit(ingest(Path(args.src), Path(args.out)))


if __name__ == "__main__":
    main()
