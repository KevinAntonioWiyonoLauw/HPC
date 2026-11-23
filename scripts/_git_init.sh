#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika

if [ ! -d .git ]; then
  git init -q
fi

# identitas lokal bila belum ada
git config user.name  >/dev/null 2>&1 || git config user.name  "HPC Project"
git config user.email >/dev/null 2>&1 || git config user.email "hpc@example.local"

git add -A
if git rev-parse HEAD >/dev/null 2>&1; then
  echo "repo sudah punya commit"
else
  git commit -q -m "Fase 0-1: fondasi repo + engine baseline + harness benchmark + generator data"
  echo "commit awal dibuat"
fi
echo "=== status ==="
git status -s
echo "=== files tracked (ringkas) ==="
git ls-files | head -40
