#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
pkill -f "uvicorn app:app" 2>/dev/null || true
sleep 1
HOST_IP=$(ip route | awk '/default/ {print $3; exit}')
export LLM_BASE_URL="http://$HOST_IP:12800/v1"
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
cd service
uvicorn app:app --host 0.0.0.0 --port 8000 > ../results/service.log 2>&1 &
SRV=$!
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
grep startup ../results/service.log || true

echo "=== /status (engines) ==="
curl -s http://127.0.0.1:8000/status | python -c "import sys,json;d=json.load(sys.stdin);print('engines=',d['engines'],'active=',d['engine_active'],'n=',d['n'])"

for ENG in baseline openmp cuda; do
  echo "=== /engine -> $ENG ; /search ==="
  curl -s -X POST http://127.0.0.1:8000/engine -H "Content-Type: application/json" -d "{\"name\":\"$ENG\"}" >/dev/null
  curl -s -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" \
    -d '{"query":"berapa uang harian perjalanan dinas luar kota","k":3}' \
    | python -c "import sys,json;d=json.load(sys.stdin);print(' engine=',d['engine'],'retrieval_ms=',d['retrieval_ms'],'top1=',d['results'][0]['meta']['sop'],d['results'][0]['meta']['pasal'])"
done

echo "=== /ask (cuda, LLM) ==="
curl -s -X POST http://127.0.0.1:8000/engine -H "Content-Type: application/json" -d '{"name":"cuda"}' >/dev/null
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"query":"Apakah lisensi 40 juta butuh dua penawaran pembanding?","k":3,"use_llm":true}' \
  | python -c "import sys,json;d=json.load(sys.stdin);print('llm_status=',d['llm_status'],'retrieval_ms=',d['latency']['retrieval_ms']);print('answer=',(d['answer'] or '')[:200])"

kill $SRV 2>/dev/null || true
echo done
