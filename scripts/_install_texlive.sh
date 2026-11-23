#!/usr/bin/env bash
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
LOG=/mnt/g/Project/Kuliah/HPC/hpc-knn-sika/results/texlive_install.log
{
  echo "=== apt update ==="
  apt-get update -qq
  echo "=== install texlive subset ==="
  apt-get install -y -qq texlive-latex-base texlive-latex-recommended \
      texlive-latex-extra texlive-pictures texlive-fonts-recommended \
      texlive-lang-other
  echo "=== versi ==="
  pdflatex --version | head -1
  echo "=== DONE ==="
} > "$LOG" 2>&1
echo "texlive selesai -> $LOG"
