#!/usr/bin/env python3
"""fetch_jdih.py - ambil regulasi publik nyata (JDIH BPK) dan potong per pasal.

Alur otomatis (dapat diulang, tanpa langkah manual):
  1. Cari di peraturan.bpk.go.id per kata kunci tema (pengadaan, data pribadi,
     perjalanan dinas).
  2. Untuk tiap hasil, buka halaman Detail, ambil judul, tahun, dan tautan PDF.
  3. Unduh PDF, ekstrak teks dengan `pdftotext`.
  4. Potong per pasal (baris "Pasal N"), buang bagian menimbang/dasar hukum.
  5. Tulis markdown per regulasi ke data/sop_synthetic/ (format yang dibaca
     scripts/build_corpus.py) + manifest JSON.

Regulasi perundang-undangan Indonesia berstatus dokumen publik, sehingga teksnya
boleh disimpan untuk reproduksi.

Contoh:
  python scripts/fetch_jdih.py --limit-per-cat 20
  python scripts/build_corpus.py --filler 15000   # gabung real + filler
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://peraturan.bpk.go.id"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

CATEGORIES = {
    "pengadaan": ("Pengadaan Barang/Jasa", [
        "pengadaan%20barang%20jasa", "pengadaan%20pemerintah",
        "peraturan%20pengadaan%20barang%20jasa",
    ]),
    "datapribadi": ("Pelindungan Data Pribadi", [
        "data%20pribadi", "pelindungan%20data%20pribadi",
        "informasi%20dan%20transaksi%20elektronik",
    ]),
    "perjalanandinas": ("Perjalanan Dinas", [
        "perjalanan%20dinas", "biaya%20perjalanan%20dinas",
        "uang%20harian%20perjalanan%20dinas",
    ]),
}

PASAL_LINE = re.compile(r"^\s*Pasal\s+(\d+[A-Za-z]?)\s*\.?\s*$")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def search_details(keyword: str, limit: int):
    html = fetch_html(f"{BASE}/Search?keywords={keyword}")
    links = re.findall(r'href="(/Details/\d+/[^"]+)"', html)
    seen, out = set(), []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out[:limit]


def parse_details(detail_path: str):
    html = fetch_html(BASE + detail_path)
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else detail_path
    title = title.replace(" - JDIH BPK", "").strip()
    year = ""
    ym = re.search(r"Tahun\s+(\d{4})", title) or re.search(r"(\d{4})", detail_path)
    if ym:
        year = ym.group(1)
    pdf = re.search(r'href="(/Download/\d+/[^"]+\.pdf)"', html) or \
        re.search(r'href="(/Read/\d+/[^"]+\.pdf)"', html)
    pdf_path = pdf.group(1) if pdf else None
    return {"title": title, "year": year, "pdf": pdf_path, "detail": detail_path}


def code_from_detail(detail_path: str, title: str) -> str:
    # slug seperti peraturan-lkpp-no-5-tahun-2021 / uu-no-27-tahun-2022
    slug = detail_path.strip("/").split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").upper()
    return slug[:60] or "REG"


def pdf_to_text(pdf_bytes: bytes, workdir: Path, stem: str) -> str:
    pdf_path = workdir / f"{stem}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    txt_path = workdir / f"{stem}.txt"
    try:
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf_path), str(txt_path)],
                       check=True, capture_output=True, timeout=120)
    except Exception as e:
        print(f"  pdftotext gagal: {e}", file=sys.stderr)
        return ""
    return txt_path.read_text(encoding="utf-8", errors="replace")


def split_pasal(text: str):
    """Kembalikan list[(nomor, isi)] dari teks PDF. Hanya baris 'Pasal N' murni
    yang dianggap batas (referensi seperti 'Pasal 5 ayat (1), Pasal 20' diabaikan)."""
    lines = text.splitlines()
    pasal = []
    cur_no, cur = None, []
    started = False
    for raw in lines:
        line = raw.rstrip()
        m = PASAL_LINE.match(line)
        # heuristik: mulai hanya setelah menemukan 'Pasal 1' atau setelah bagian
        # 'BAB' pertama agar tidak menangkap daftar dasar hukum di awal.
        if m:
            no = m.group(1)
            if cur_no is not None:
                body = " ".join(t.strip() for t in cur if t.strip())
                if body:
                    pasal.append((cur_no, body))
            cur_no, cur = no, []
            started = True
            continue
        if started and line.strip():
            # buang header/footer berulang yang umum di PDF salinan
            low = line.strip().lower()
            if low in ("presiden republik indonesia", "salinan", "repuelik indonesia"):
                continue
            cur.append(line)
    if cur_no is not None:
        body = " ".join(t.strip() for t in cur if t.strip())
        if body:
            pasal.append((cur_no, body))
    # bersihkan: gabungkan spasi ganda, buang nomor halaman murni
    cleaned = []
    for no, body in pasal:
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) < 20:
            continue
        cleaned.append((no, body))
    return cleaned


def to_markdown(code: str, title: str, year: str, unit: str, pasal) -> str:
    out = [f"# {code} | {title} | {year or '0'} | {unit}"]
    for no, body in pasal:
        out.append(f"## Pasal {no}")
        out.append(body)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "sop_synthetic"))
    ap.add_argument("--rawdir", default=str(ROOT / "data" / "jdih_raw" / "pdf"))
    ap.add_argument("--limit-per-cat", type=int, default=20)
    ap.add_argument("--only", default="", help="batasi ke satu kategori")
    ap.add_argument("--manifest", default=str(ROOT / "data" / "jdih_raw" / "manifest.json"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    raw_dir = Path(args.rawdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    used_codes = set()
    for cat, (unit, keywords) in CATEGORIES.items():
        if args.only and args.only != cat:
            continue
        print(f"\n== Kategori {cat} ({unit}) ==")
        details = []
        for kw in keywords:
            try:
                details += search_details(kw, args.limit_per_cat)
            except Exception as e:
                print(f"  search '{kw}' gagal: {e}", file=sys.stderr)
        # unik, batasi
        uniq, seen = [], set()
        for d in details:
            if d not in seen:
                seen.add(d)
                uniq.append(d)
        uniq = uniq[: args.limit_per_cat]
        print(f"  {len(uniq)} kandidat dokumen")
        got = 0
        for d in uniq:
            try:
                info = parse_details(d)
            except Exception as e:
                print(f"  detail gagal {d}: {e}", file=sys.stderr)
                continue
            if not info["pdf"]:
                continue
            code = code_from_detail(d, info["title"])
            if code in used_codes:
                continue
            stem = code.lower().replace("/", "_")
            try:
                txt = pdf_to_text(fetch_bytes(BASE + info["pdf"]), raw_dir, stem)
            except Exception as e:
                print(f"  unduh gagal {code}: {e}", file=sys.stderr)
                continue
            if not txt:
                continue
            pasal = split_pasal(txt)
            if len(pasal) < 3:
                continue
            used_codes.add(code)
            md = to_markdown(code, info["title"], info["year"], unit, pasal)
            (out_dir / f"{stem}.md").write_text(md, encoding="utf-8")
            manifest.append({"code": code, "title": info["title"], "year": info["year"],
                             "unit": unit, "pasal": len(pasal), "detail": d})
            got += 1
            print(f"  + {code}: {len(pasal)} pasal ({info['year']})")

    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(m["pasal"] for m in manifest)
    print(f"\nSelesai: {len(manifest)} regulasi, {total} pasal. Manifest -> {args.manifest}")


if __name__ == "__main__":
    main()
