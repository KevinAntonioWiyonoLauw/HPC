#!/usr/bin/env bash
set +e
echo "=== default gateway (host IP dari WSL) ==="
GW=$(ip route | awk '/default/ {print $3; exit}')
echo "gateway=$GW"
RESOLV=$(grep -m1 nameserver /etc/resolv.conf | awk '{print $2}')
echo "resolv_ns=$RESOLV"

KEY="pn-carte-S3RWRJbHsqS5XuWP"
for HOST in 127.0.0.1 "$RESOLV" "$GW"; do
  echo "--- coba http://$HOST:12800/v1/models ---"
  curl -s -m 5 -o /dev/null -w "http_code=%{http_code} time=%{time_total}s\n" \
    -H "Authorization: Bearer $KEY" "http://$HOST:12800/v1/models" || echo "gagal konek"
done
