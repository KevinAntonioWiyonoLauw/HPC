#!/usr/bin/env python3
"""test_units.py — uji unit ringan untuk skrip di scripts/ (dipakai CI).

Tidak butuh GPU, model embedding, atau torch. Fokus pada logika murni:
  - data/gen_synthetic.py: bentuk, dtype, dan reproducibility (seed tetap).
  - scripts/build_corpus.py: gen_filler, build_items, dan parser markdown pasal.

Jalankan: python scripts/test_units.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGenSynthetic(unittest.TestCase):
    def test_shapes_dtype_and_reproducible(self):
        gen = os.path.join(ROOT, "data", "gen_synthetic.py")
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            for d in (d1, d2):
                subprocess.run([sys.executable, gen, "--n", "50", "--d", "8",
                                "--q", "7", "--seed", "123", "--outdir", d],
                               check=True, capture_output=True)
            b1 = np.fromfile(os.path.join(d1, "basis_50_8.bin"), dtype=np.float32)
            b2 = np.fromfile(os.path.join(d2, "basis_50_8.bin"), dtype=np.float32)
            q1 = np.fromfile(os.path.join(d1, "queries_7_8.bin"), dtype=np.float32)
            self.assertEqual(b1.size, 50 * 8)
            self.assertEqual(q1.size, 7 * 8)
            self.assertEqual(b1.dtype, np.float32)
            self.assertTrue(np.array_equal(b1, b2), "seed sama harus identik")
            self.assertTrue((b1 >= 0).all() and (b1 < 1).all())
            with open(os.path.join(d1, "meta_50_8.json")) as f:
                meta = json.load(f)
            self.assertEqual((meta["n"], meta["d"], meta["q"]), (50, 8, 7))


class TestBuildCorpus(unittest.TestCase):
    def setUp(self):
        self.bc = _load_module(os.path.join(ROOT, "scripts", "build_corpus.py"), "build_corpus")

    def test_gen_filler_count_and_determinism(self):
        a = self.bc.gen_filler(20, seed=7)
        b = self.bc.gen_filler(20, seed=7)
        self.assertEqual(len(a), 20)
        self.assertEqual([x["text"] for x in a], [x["text"] for x in b])
        for it in a:
            self.assertIn("text", it)
            self.assertIn("meta", it)
            self.assertTrue(it["meta"]["sop"].startswith("REF-"))

    def test_build_items_flattens_pasal(self):
        docs = [{
            "sop": "SOP-X", "judul": "Uji", "tahun": 2024, "unit": "Unit",
            "pasal": [("Pasal 1", "isi satu"), ("Pasal 2", "isi dua")],
        }]
        items = self.bc.build_items(docs)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["meta"]["sop"], "SOP-X")
        self.assertEqual(items[1]["meta"]["pasal"], "Pasal 2")

    def test_pasal_regex(self):
        m = self.bc.PASAL_RE.match("Pasal 12A. Isi pasal")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "Pasal 12A")
        self.assertEqual(m.group(2), "Isi pasal")

    def test_fetch_jdih_split_pasal(self):
        fj = _load_module(os.path.join(ROOT, "scripts", "fetch_jdih.py"), "fetch_jdih")
        # Teks mirip hasil pdftotext: dasar hukum (referensi Pasal di tengah kalimat
        # harus diabaikan), lalu pasal-pasal asli.
        text = (
            "Menimbang bahwa berdasarkan Pasal 5 ayat (1), Pasal 20 UUD 1945;\n"
            "MEMUTUSKAN:\n"
            "Pasal 1\n"
            "Dalam Undang-Undang ini yang dimaksud dengan data pribadi adalah data\n"
            "tentang orang perseorangan yang teridentifikasi.\n"
            "Pasal 2\n"
            "(1) Undang-Undang ini berlaku untuk pemrosesan data pribadi.\n"
            "(2) Ketentuan sebagaimana dimaksud pada ayat (1) berlaku umum.\n"
            "Pasal 3\n"
            "Pemrosesan data pribadi dilakukan berdasarkan asas pelindungan.\n"
        )
        pasal = fj.split_pasal(text)
        nos = [p[0] for p in pasal]
        self.assertEqual(nos, ["1", "2", "3"], nos)
        self.assertTrue(all(len(b) >= 20 for _, b in pasal))
        md = fj.to_markdown("UU-UJI", "Contoh UU", "2024", "Unit Uji", pasal)
        self.assertIn("## Pasal 2", md)
        self.assertTrue(md.startswith("# UU-UJI | Contoh UU | 2024 | Unit Uji"))

    def test_ingest_jdih_parse_and_markdown(self):
        ij = _load_module(os.path.join(ROOT, "scripts", "ingest_jdih.py"), "ingest_jdih")
        sample = ("SOP-UJI-01 | Contoh Aturan | 2024 | Unit Uji\n"
                  "Pasal 1\nIsi satu.\nPasal 2\nIsi dua.\nPasal 3A\nIsi tiga A.\n")
        header, pasal = ij.parse_regulation(sample)
        self.assertEqual(header["sop"], "SOP-UJI-01")
        self.assertEqual(header["judul"], "Contoh Aturan")
        self.assertEqual(len(pasal), 3)
        self.assertEqual(pasal[2][0], "Pasal 3A")
        md = ij.to_markdown(header, pasal, "contoh")
        self.assertTrue(md.startswith("# SOP-UJI-01 | Contoh Aturan | 2024 | Unit Uji"))
        self.assertIn("## Pasal 2", md)
        # markdown hasil harus terbaca kembali oleh build_corpus
        import pathlib
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "contoh.md").write_text(md, encoding="utf-8")
            docs = self.bc.load_markdown_docs(pathlib.Path(d))
        self.assertEqual(len(docs), 1)
        self.assertEqual(len(self.bc.build_items(docs)), 3)

    def test_sample_docs_nonempty(self):
        self.assertGreater(len(self.bc.SAMPLE_DOCS), 0)
        items = self.bc.build_items(self.bc.SAMPLE_DOCS)
        self.assertGreater(len(items), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
