#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate

HOST_IP=$(ip route | awk '/default/ {print $3; exit}')
BASE=$(grep -E '^LLM_BASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- || true)
BASE=${BASE:-http://localhost:12800/v1}
BASE=${BASE/localhost/$HOST_IP}
BASE=${BASE/127.0.0.1/$HOST_IP}
export LLM_BASE_URL="$BASE"
echo "efektif LLM_BASE_URL=$LLM_BASE_URL"

cd service
uvicorn app:app --host 127.0.0.1 --port 8000 > ../results/service.log 2>&1 &
SRV=$!
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 1
done

echo "=== /models ==="
curl -s http://127.0.0.1:8000/models | python -c "import sys,json;d=json.load(sys.stdin);print('n_models=',len(d.get('models',[])));print('current=',d.get('current'));print('contoh=',d.get('models',[])[:5])"
echo
echo "=== /ask (use_llm=true) ==="
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"query":"Apakah pembelian lisensi perangkat lunak 40 juta perlu dua penawaran pembanding?","k":3,"use_llm":true}' \
  | python -c "import sys,json;d=json.load(sys.stdin);print('llm_status=',d['llm_status']);print('latency=',d['latency']);print('answer=\n',(d['answer'] or '')[:700])"

kill $SRV 2>/dev/null || true
echo "done"
