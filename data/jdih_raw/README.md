# data/jdih_raw — tempat menaruh regulasi publik (JDIH) asli

Letakkan berkas `.txt`/`.md` regulasi yang sudah diunduh dari sumber resmi di sini
(satu berkas per aturan). Skrip `scripts/ingest_jdih.py` mengubahnya menjadi format
korpus SOP yang dibaca `scripts/build_corpus.py`.

Format tiap berkas:
```
<kode SOP> | <judul> | <tahun> | <unit>
Pasal 1
Isi pasal pertama ...
Pasal 2
Isi pasal kedua ...
```

Contoh sumber resmi: https://peraturan.go.id , JDIH kementerian/lembaga.

Proyek ini tidak menyertakan teks hukum berhak cipta; berkas yang Anda unduh
tidak di-commit (lihat .gitignore: `data/jdih_raw/*.txt`).
