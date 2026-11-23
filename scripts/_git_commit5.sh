#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
git add -A
git commit -q -m "Fase 5: generator laporan (REPORT.md) + build_corpus skala besar (filler 20k) + pilihan korpus via env" || echo "no changes"
git --no-pager log --oneline -3
