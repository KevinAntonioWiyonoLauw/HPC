#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

# WSL2 (NAT) tidak bisa menjangkau localhost Windows. Terjemahkan host localhost
# pada LLM_BASE_URL ke IP gateway (host Windows) secara otomatis.
HOST_IP=$(ip route | awk '/default/ {print $3; exit}')
BASE=$(grep -E '^LLM_BASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
BASE=${BASE:-http://localhost:12800/v1}
BASE=${BASE/localhost/$HOST_IP}
BASE=${BASE/127.0.0.1/$HOST_IP}
export LLM_BASE_URL="$BASE"
echo "LLM_BASE_URL (efektif) = $LLM_BASE_URL"

cd service
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
exec uvicorn app:app --host 0.0.0.0 --port 8000
