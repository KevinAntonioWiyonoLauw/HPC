#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
pkill -f "uvicorn app:app" 2>/dev/null || true
sleep 1
HOST_IP=$(ip route | awk '/default/ {print $3; exit}')
BASE=$(grep -E '^LLM_BASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
BASE=${BASE:-http://localhost:12800/v1}; BASE=${BASE/localhost/$HOST_IP}
export LLM_BASE_URL="$BASE"

cd service
uvicorn app:app --host 127.0.0.1 --port 8000 > ../results/service.log 2>&1 &
SRV=$!
echo "menunggu server + warmup embedding..."
for i in $(seq 1 90); do curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
grep "startup" ../results/service.log || true

echo "=== /ask #1 (use_llm=false) ==="
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"query":"berapa uang harian perjalanan dinas luar kota?","k":3,"use_llm":false}' \
  | python -c "import sys,json;d=json.load(sys.stdin);print('latency=',d['latency']);print('top1=',d['citations'][0]['meta']['sop'],d['citations'][0]['meta']['pasal'])"

echo "=== /ask #2 (use_llm=true) ==="
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"query":"berapa uang harian perjalanan dinas luar kota?","k":3,"use_llm":true}' \
  | python -c "import sys,json;d=json.load(sys.stdin);print('llm_status=',d['llm_status']);print('latency=',d['latency']);print('answer=',(d['answer'] or '')[:400])"

kill $SRV 2>/dev/null || true
echo done
