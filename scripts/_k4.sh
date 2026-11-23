#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
pkill -f "uvicorn app:app" 2>/dev/null || true
sleep 1
export SIKA_BASIS_FILE="$(pwd)/data/out/basis_100000_384.bin"
export SIKA_N=100000
export SIKA_D=384
export OMP_NUM_THREADS=4
HOST_IP=$(ip route | awk '/default/ {print $3; exit}')
export LLM_BASE_URL="http://$HOST_IP:12800/v1"

cd service
uvicorn app:app --host 127.0.0.1 --port 8000 > ../results/service_k4.log 2>&1 &
SRV=$!
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
grep startup ../results/service_k4.log || true
echo "=== /status ==="
curl -s http://127.0.0.1:8000/status | python -c "import sys,json;d=json.load(sys.stdin);print('n=',d['n'],'dim=',d['dim'],'source=',d['source'],'engines=',d['engines'])"

for ENG in baseline openmp; do
  echo "=== K4: /bench 300x engine=$ENG (N=100000, D=384) ==="
  curl -s -X POST http://127.0.0.1:8000/engine -H "Content-Type: application/json" -d "{\"name\":\"$ENG\"}" >/dev/null
  curl -s -X POST http://127.0.0.1:8000/bench -H "Content-Type: application/json" \
    -d '{"query":"berapa uang harian perjalanan dinas luar kota","n":300,"k":10}' \
    | python -c "import sys,json;d=json.load(sys.stdin);print('engine=',d['engine'],'p50=',d['p50_ms'],'p95=',d['p95_ms'],'p99=',d['p99_ms'],'qps=',d['qps'],'K4(openmp p95<=100)=', d['p95_ms']<=100 if d['engine']=='openmp' else '-')"
done

kill $SRV 2>/dev/null || true
echo done
