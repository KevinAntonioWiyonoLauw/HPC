#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
cd service
# start server di background
uvicorn app:app --host 127.0.0.1 --port 8000 > ../results/service.log 2>&1 &
SRV=$!
echo "server pid=$SRV"
# tunggu siap
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then echo "ready after ${i}s"; break; fi
  sleep 1
done

echo "=== /status ==="
curl -s http://127.0.0.1:8000/status
echo
echo "=== /search ==="
curl -s -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" \
  -d '{"query":"Apakah pembelian lisensi perangkat lunak 40 juta perlu dua penawaran pembanding?","k":3}'
echo
echo "=== /ask (use_llm=false) ==="
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"query":"Apakah pembelian lisensi perangkat lunak 40 juta perlu dua penawaran pembanding?","k":3,"use_llm":false}'
echo
echo "=== /engine -> openmp ==="
curl -s -X POST http://127.0.0.1:8000/engine -H "Content-Type: application/json" -d '{"name":"openmp"}'
echo
echo "=== /bench 50x ==="
curl -s -X POST http://127.0.0.1:8000/bench -H "Content-Type: application/json" \
  -d '{"query":"batas waktu klaim perjalanan dinas","n":50,"k":10}'
echo
echo "=== stop ==="
kill $SRV 2>/dev/null || true
sleep 1
echo "done"
