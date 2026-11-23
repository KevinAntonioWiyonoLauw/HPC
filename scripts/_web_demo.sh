#!/usr/bin/env bash
set -euo pipefail
cd /mnt/g/Project/Kuliah/HPC/hpc-knn-sika
source .venv/bin/activate
python - <<'PY'
import json, urllib.request
BASE="http://127.0.0.1:8000"
def post(path, obj):
    req=urllib.request.Request(BASE+path, data=json.dumps(obj).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=120))
def get(path):
    return json.load(urllib.request.urlopen(BASE+path, timeout=30))

st=get("/status"); print("korpus:", st["corpus"], "n:", st["n"], "engines:", st["engines"])
Q="Apakah pembelian lisensi perangkat lunak 40 juta perlu dua penawaran pembanding?"
print("\n=== Benchmark 200 query per engine (N=%d) ===" % st["n"])
print(f"{'engine':10} {'p50':>8} {'p95':>8} {'p99':>8} {'qps':>10}")
for eng in st["engines"]:
    post("/engine", {"name":eng})
    r=post("/bench", {"query":Q,"n":200,"k":10})
    print(f"{eng:10} {r['p50_ms']:8.3f} {r['p95_ms']:8.3f} {r['p99_ms']:8.3f} {r['qps']:10.1f}")

print("\n=== /ask (engine cuda + LLM) ===")
post("/engine", {"name":"cuda"})
r=post("/ask", {"query":Q,"k":3,"use_llm":True})
print("llm_status:", r["llm_status"])
print("latency:", r["latency"])
print("answer:", (r["answer"] or "")[:400])
PY
