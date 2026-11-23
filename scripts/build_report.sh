#!/usr/bin/env bash
set -uo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika/results/report
pdflatex -interaction=nonstopmode laporan_hpc_knn.tex > pass1.log 2>&1
echo "pass1 exit=$?"
pdflatex -interaction=nonstopmode laporan_hpc_knn.tex > pass2.log 2>&1
echo "pass2 exit=$?"
echo "=== errors/warnings ==="
grep -iE "^!|error|undefined|overfull" pass2.log | head -25 || true
echo "=== hasil ==="
ls -la laporan_hpc_knn.pdf 2>/dev/null || echo "PDF TIDAK terbentuk"
echo "=== halaman ==="
grep -E "Output written" pass2.log | tail -1
