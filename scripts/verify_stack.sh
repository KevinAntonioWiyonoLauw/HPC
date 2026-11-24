#!/usr/bin/env bash
# verify_stack.sh - cek stack SIKA setelah `docker compose up`.
# Keluar dengan kode non-nol bila ada pemeriksaan yang gagal.
#
# Pemakaian:
#   bash scripts/verify_stack.sh            # default http://localhost:8000
#   API=http://host:8000 bash scripts/verify_stack.sh
set -uo pipefail

API="${API:-http://localhost:8000}"
fail=0

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "OK   $name"
  else
    echo "FAIL $name"
    fail=1
  fi
}

http_ok() { [ "$(curl -s -o /dev/null -w '%{http_code}' "$1")" = "200" ]; }

json_field() { # url, jq-free field check via grep
  local url="$1" pat="$2"
  curl -s "$url" | grep -q "$pat"
}

echo "== SIKA stack verification ($API) =="
check "GET /health"            http_ok "$API/health"
check "GET /status"            http_ok "$API/status"
check "GET /engines"           http_ok "$API/engines"
check "status has corpus/n"    json_field "$API/status" '"n"'
check "search returns results" bash -c "curl -s -X POST '$API/search' -H 'Content-Type: application/json' -d '{\"query\":\"uang harian perjalanan dinas\",\"k\":3}' | grep -q '\"results\"'"
check "ask (no llm) returns"   bash -c "curl -s -X POST '$API/ask' -H 'Content-Type: application/json' -d '{\"query\":\"uang harian perjalanan dinas\",\"k\":3,\"use_llm\":false}' | grep -q '\"citations\"'"

echo
if [ "$fail" -eq 0 ]; then
  echo "SEMUA PEMERIKSAAN LULUS"
else
  echo "ADA PEMERIKSAAN GAGAL"
fi
exit "$fail"
