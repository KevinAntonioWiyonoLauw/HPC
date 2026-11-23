#!/usr/bin/env bash
set -uo pipefail
echo "=== perbaiki state dpkg/apt ==="
export DEBIAN_FRONTEND=noninteractive
apt-get clean
dpkg --configure -a 2>&1 | tail -5
apt-get -f install -y 2>&1 | tail -8
echo "=== cuda-related paket terpasang ==="
dpkg -l | grep -iE "cuda|nvidia" | awk '{print $1, $2}' | head -30
echo "=== apakah nvcc ada ==="
which nvcc || echo "belum"
echo "=== ruang ==="
df -h / | tail -1
