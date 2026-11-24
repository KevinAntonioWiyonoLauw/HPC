#!/usr/bin/env python3
"""build_corpus.py — bangun korpus SIKA: potongan pasal + embedding MiniLM.

Sumber:
  - data/sop_synthetic/*.md  (SOP internal terkurasi; jawaban pasti utk demo)
  - filler sintetis (opsional, --filler N) untuk menaikkan skala indeks ke
    ukuran realistis (Tabel 1.2: 15.000-30.000 potongan) agar retrieval
    (dan akselerasi GPU) bermakna pada skala nyata.
  - SAMPLE_DOCS bawaan bila folder SOP kosong.

Keluaran:
  data/embeddings/<name>.f32   matriks float32 N x D (row-major)
  data/embeddings/<name>.json  {dim,n,items:[{id,text,meta:{sop,pasal,tahun,unit}}]}
"""
import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "service"))

SAMPLE_DOCS = [
    {
        "sop": "SOP-PGD-01", "judul": "Pengadaan Barang dan Jasa", "tahun": 2024, "unit": "Unit Pengadaan",
        "pasal": [
            ("Pasal 1", "Ruang lingkup SOP ini mencakup seluruh pengadaan barang dan jasa di lingkungan institusi, termasuk pengadaan perangkat lunak, perangkat keras, jasa konsultansi, dan jasa lainnya, dengan sumber dana internal maupun anggaran negara."),
            ("Pasal 2", "Setiap pengadaan perangkat lunak (lisensi) dengan nilai sampai dengan Rp50.000.000 wajib menyertakan minimal dua penawaran pembanding dari penyedia yang berbeda sebelum penunjukan dilakukan."),
            ("Pasal 3", "Pengadaan dengan nilai di atas Rp50.000.000 sampai dengan Rp200.000.000 wajib melalui proses pemilihan penyedia dengan minimal tiga penawaran dan berita acara evaluasi harga."),
            ("Pasal 4", "Pengadaan dengan nilai di atas Rp200.000.000 wajib melalui tender terbuka dan persetujuan pejabat pengadaan serta unit kepatuhan."),
            ("Pasal 5", "Penunjukan langsung hanya diperbolehkan untuk pengadaan mendesak dengan nilai di bawah Rp10.000.000 dan harus dilaporkan kepada unit kepatuhan paling lambat tiga hari kerja setelah transaksi."),
            ("Pasal 6", "Dokumen penawaran pembanding wajib disimpan sebagai lampiran berita acara pengadaan dan dapat diaudit sewaktu-waktu."),
        ],
    },
    {
        "sop": "SOP-PGD-02", "judul": "Pengadaan Perangkat Lunak dan Lisensi", "tahun": 2024, "unit": "Unit Teknologi Informasi",
        "pasal": [
            ("Pasal 1", "Pembelian lisensi perangkat lunak senilai Rp40.000.000 termasuk dalam kategori pengadaan bernilai sampai dengan Rp50.000.000 sehingga memerlukan dua penawaran pembanding."),
            ("Pasal 2", "Lisensi perangkat lunak yang bersifat langganan tahunan (subscription) harus mencantumkan periode, jumlah pengguna, dan mekanisme perpanjangan dalam kontrak."),
            ("Pasal 3", "Perangkat lunak yang menyimpan data pribadi wajib memenuhi ketentuan pengelolaan data pribadi sebagaimana diatur pada SOP-PDP-01."),
            ("Pasal 4", "Pengadaan lisensi dengan nilai di atas Rp100.000.000 memerlukan kajian kelayakan teknis dan persetujuan kepala unit teknologi informasi."),
        ],
    },
    {
        "sop": "SOP-PDP-01", "judul": "Pengelolaan Data Pribadi", "tahun": 2023, "unit": "Unit Kepatuhan",
        "pasal": [
            ("Pasal 1", "Institusi wajib melindungi data pribadi yang dikumpulkan, diolah, dan disimpan, sesuai dengan prinsip pembatasan tujuan dan minimalisasi data."),
            ("Pasal 2", "Transfer data pribadi ke pihak ketiga atau layanan di luar infrastruktur institusi hanya diperbolehkan dengan persetujuan tertulis dari subjek data dan persetujuan unit kepatuhan."),
            ("Pasal 3", "Layanan kecerdasan buatan yang memproses data pribadi wajib dijalankan pada infrastruktur on-premise; pengiriman data pribadi ke layanan publik di luar organisasi dilarang."),
            ("Pasal 4", "Setiap insiden kebocoran data pribadi wajib dilaporkan kepada unit kepatuhan dalam waktu 72 jam dan kepada subjek data dalam waktu 14 hari."),
            ("Pasal 5", "Data pribadi yang tidak lagi diperlukan harus dimusnahkan secara aman paling lambat dua tahun setelah tujuan pemrosesan berakhir."),
        ],
    },
    {
        "sop": "SOP-PD-01", "judul": "Perjalanan Dinas", "tahun": 2024, "unit": "Unit Keuangan",
        "pasal": [
            ("Pasal 1", "Perjalanan dinas dalam negeri untuk pegawai golongan tertentu diberikan biaya transportasi, uang harian, dan biaya penginapan sesuai standar yang berlaku."),
            ("Pasal 2", "Uang harian perjalanan dinas dalam kota ditetapkan sebesar Rp150.000 per hari dan untuk luar kota sebesar Rp380.000 per hari."),
            ("Pasal 3", "Penginapan untuk perjalanan dinas luar kota dibatasi maksimal Rp1.200.000 per malam untuk kota besar dan Rp800.000 untuk kota lainnya."),
            ("Pasal 4", "Perjalanan dinas luar negeri memerlukan persetujuan direktur dan mengikuti standar biaya yang ditetapkan oleh menteri keuangan."),
            ("Pasal 5", "Klaim perjalanan dinas wajib dilengkapi bukti pengeluaran asli dan diserahkan paling lambat 14 hari kerja setelah perjalanan selesai."),
        ],
    },
    {
        "sop": "SOP-KEU-02", "judul": "Reimbursement dan Klaim Biaya", "tahun": 2024, "unit": "Unit Keuangan",
        "pasal": [
            ("Pasal 1", "Klaim reimbursement atas biaya operasional wajib dilengkapi bukti pembayaran yang sah dan disetujui atasan langsung."),
            ("Pasal 2", "Batas waktu pengajuan reimbursement adalah 30 hari kalender sejak pengeluaran terjadi; klaim melewati batas dapat ditolak."),
            ("Pasal 3", "Klaim di atas Rp25.000.000 memerlukan verifikasi tambahan dari unit kepatuhan sebelum pembayaran."),
        ],
    },
    {
        "sop": "SOP-SEC-01", "judul": "Keamanan Informasi dan Akses", "tahun": 2023, "unit": "Unit Teknologi Informasi",
        "pasal": [
            ("Pasal 1", "Akses terhadap sistem internal wajib menggunakan autentikasi dan otorisasi berbasis peran (role-based access control)."),
            ("Pasal 2", "Kata sandi wajib diganti setiap 90 hari dan tidak boleh digunakan ulang untuk tiga kata sandi terakhir."),
            ("Pasal 3", "Akses istimewa (administrator) harus melalui persetujuan dan dicatat dalam log audit yang tidak dapat diubah."),
            ("Pasal 4", "Perangkat yang mengakses jaringan internal wajib terdaftar dan memiliki perlindungan enkripsi data."),
        ],
    },
    {
        "sop": "SOP-AUD-01", "judul": "Audit Internal dan Temuan", "tahun": 2024, "unit": "Unit Audit Internal",
        "pasal": [
            ("Pasal 1", "Audit internal dilakukan minimal satu kali per tahun terhadap seluruh unit kerja."),
            ("Pasal 2", "Temuan audit wajib ditindaklanjuti dengan rencana perbaikan paling lambat 30 hari setelah laporan diterima."),
            ("Pasal 3", "Temuan yang berkaitan dengan penunjukan vendor tanpa penawaran pembanding dikategorikan sebagai temuan signifikan dan wajib dilaporkan kepada direksi."),
        ],
    },
    {
        "sop": "SOP-HRD-01", "judul": "Cuti dan Kehadiran Pegawai", "tahun": 2024, "unit": "Unit Sumber Daya Manusia",
        "pasal": [
            ("Pasal 1", "Setiap pegawai berhak atas cuti tahunan sebanyak 12 hari kerja setelah bekerja minimal satu tahun."),
            ("Pasal 2", "Pengajuan cuti wajib dilakukan paling lambat tiga hari kerja sebelum tanggal cuti melalui sistem kepegawaian."),
            ("Pasal 3", "Cuti sakit lebih dari dua hari wajib dilengkapi surat keterangan dokter."),
        ],
    },
]

# --- filler sintetis: kalimat administratif acak untuk menaikkan skala ---
FILLER_SUBJECT = ["unit kerja", "pejabat berwenang", "staf pelaksana", "tim teknis", "bagian keuangan",
                  "unit kepatuhan", "penyedia jasa", "atasan langsung", "panitia pengadaan", "auditor internal",
                  "kepala unit", "sekretariat", "bidang operasional", "koordinator wilayah", "bendahara"]
FILLER_ACTION = ["wajib menyampaikan laporan", "harus melakukan verifikasi", "berkewajiban menyimpan dokumen",
                 "bertanggung jawab atas pencatatan", "diminta menandatangani berita acara", "melakukan reviu berkala",
                 "menyusun rencana kerja", "melaporkan hasil pelaksanaan", "melakukan pengarsipan", "mengoordinasikan pelaksanaan"]
FILLER_OBJECT = ["sesuai ketentuan yang berlaku", "paling lambat akhir bulan", "dengan tembusan kepada pimpinan",
                 "melalui sistem informasi internal", "untuk keperluan audit", "sebagai bahan evaluasi",
                 "dalam rangka pengendalian internal", "tanpa mengabaikan aspek kerahasiaan", "secara tertulis dan terdokumentasi",
                 "dengan memperhatikan efisiensi anggaran"]
FILLER_TOPIC = ["pengadaan", "perjalanan dinas", "pengelolaan data", "keamanan informasi", "pengarsipan dokumen",
                "pelaporan keuangan", "pemeliharaan aset", "pengelolaan SDM", "kepatuhan internal", "manajemen risiko"]


def gen_filler(n, seed=7):
    rng = random.Random(seed)
    items = []
    for i in range(n):
        topic = rng.choice(FILLER_TOPIC)
        text = (f"Dalam kaitannya dengan {topic}, {rng.choice(FILLER_SUBJECT)} "
                f"{rng.choice(FILLER_ACTION)} {rng.choice(FILLER_OBJECT)}.")
        sop = f"REF-{rng.randint(1,300):03d}"
        items.append({
            "text": text,
            "meta": {"sop": sop, "judul": f"Ketentuan {topic.title()}", "pasal": f"Pasal {rng.randint(1,40)}",
                     "tahun": rng.choice([2021, 2022, 2023, 2024]), "unit": "Unit Referensi", "filler": True},
        })
    return items


PASAL_RE = re.compile(r"^(Pasal\s+\d+[A-Za-z]?)\.?\s*(.*)$", re.IGNORECASE)


def load_markdown_docs(folder: Path):
    docs = []
    for path in sorted(folder.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        header = {"sop": path.stem, "judul": "", "tahun": 0, "unit": ""}
        pasal = []
        cur_no, cur_text = None, []

        def flush():
            nonlocal cur_no, cur_text
            if cur_no and cur_text:
                pasal.append((cur_no, " ".join(t.strip() for t in cur_text if t.strip())))
            cur_no, cur_text = None, []

        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                parts = [p.strip() for p in line[2:].split("|")]
                if len(parts) >= 1: header["sop"] = parts[0]
                if len(parts) >= 2: header["judul"] = parts[1]
                if len(parts) >= 3 and parts[2].isdigit(): header["tahun"] = int(parts[2])
                if len(parts) >= 4: header["unit"] = parts[3]
            elif line.startswith("## "):
                flush(); cur_no = line[3:].strip()
            elif line.strip():
                if cur_no is None: cur_no = "Pasal 1"
                cur_text.append(line)
        flush()
        if pasal:
            docs.append({**header, "pasal": pasal})
    return docs


def build_items(docs):
    items = []
    for d in docs:
        for no, text in d["pasal"]:
            items.append({"text": text, "meta": {"sop": d.get("sop", ""), "judul": d.get("judul", ""),
                          "pasal": no, "tahun": d.get("tahun", 0), "unit": d.get("unit", "")}})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sop-dir", default=str(ROOT / "data" / "sop_synthetic"))
    ap.add_argument("--real-dir", default=str(ROOT / "data" / "jdih_md"),
                    help="folder markdown regulasi publik nyata (hasil fetch_jdih.py)")
    ap.add_argument("--outdir", default=str(ROOT / "data" / "embeddings"))
    ap.add_argument("--name", default="sika")
    ap.add_argument("--filler", type=int, default=0, help="jumlah potongan filler sintetis")
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    args = ap.parse_args()

    docs = []
    # 1) Regulasi publik nyata (sumber utama) bila folder tersedia
    if args.real_dir and os.path.isdir(args.real_dir):
        real_docs = load_markdown_docs(Path(args.real_dir))
        if real_docs:
            docs += real_docs
            print(f"Regulasi nyata: {len(real_docs)} dokumen dari {args.real_dir}")
    # 2) SOP terkurasi / sintetis (untuk pertanyaan demo yang butuh jawaban pasti)
    curated_docs = load_markdown_docs(Path(args.sop_dir))
    if curated_docs:
        docs += curated_docs
        print(f"SOP terkurasi: {len(curated_docs)} dokumen dari {args.sop_dir}")
    if not docs:
        print("Tidak ada markdown -> memakai SAMPLE_DOCS bawaan")
        docs = SAMPLE_DOCS

    items = build_items(docs)
    n_curated = len(items)
    if args.filler > 0:
        items += gen_filler(args.filler)
    for i, it in enumerate(items):
        it["id"] = i
    print(f"Potongan: {n_curated} (nyata+kurasi) + {args.filler} filler = {len(items)}")

    from embed import Embedder
    emb = Embedder(args.model, "cpu")
    texts = [f"{it['meta']['sop']} {it['meta']['pasal']}. {it['text']}" for it in items]
    print("Meng-embedding... (unduh model bila pertama kali)")
    mat = emb.encode(texts)
    n, dim = mat.shape
    print(f"Embedding selesai: {n} x {dim}")

    os.makedirs(args.outdir, exist_ok=True)
    vec_path = os.path.join(args.outdir, f"{args.name}.f32")
    meta_path = os.path.join(args.outdir, f"{args.name}.json")
    mat.astype("float32").tofile(vec_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"dim": dim, "n": n, "items": items}, f, ensure_ascii=False)
    print(f"OK -> {vec_path}\nOK -> {meta_path}")


if __name__ == "__main__":
    main()
