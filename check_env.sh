#!/usr/bin/env bash
set -euo pipefail

ok() { printf "\033[32m✔\033[0m %s\n" "$1"; }
warn() { printf "\033[33m⚠\033[0m %s\n" "$1"; }
fail() { printf "\033[31m✖\033[0m %s\n" "$1"; }

missing=0
need_cmd() {
  if command -v "$1" >/dev/null 2>&1; then ok "$1 found: $(command -v "$1")"; else fail "$1 missing"; missing=1; fi
}

printf "\n🛡️  AgriShield Starter Kit Environment Check\n\n"
need_cmd git
need_cmd node
need_cmd npm
need_cmd python3
need_cmd curl

if command -v firebase >/dev/null 2>&1; then ok "firebase CLI found"; else warn "firebase CLI not found; needed only for Firebase Hosting deploys"; fi
if command -v docker >/dev/null 2>&1; then ok "docker found"; else warn "docker not found; optional for containerized deployments"; fi
if command -v mosquitto_pub >/dev/null 2>&1; then ok "mosquitto_pub found"; else warn "mosquitto_pub not found; optional for MQTT telemetry testing"; fi

printf "\nVersions:\n"
node --version 2>/dev/null || true
npm --version 2>/dev/null || true
python3 --version 2>/dev/null || true
git --version 2>/dev/null || true

printf "\nEnvironment variables to configure per project:\n"
printf "%s\n" "- GEMINI_API_KEY       optional, required for Gemini crop vision"
printf "%s\n" "- FIREBASE_CREDENTIALS optional, backend persistence"
printf "%s\n" "- VITE_API_URL         optional, frontend API override"
printf "%s\n" "- MQTT_URL             optional, telemetry broker"

if [ "$missing" -eq 0 ]; then
  printf "\n✅ Environment has the required core tools.\n"
else
  printf "\n❌ Some required tools are missing. Install them before scaffolding.\n"
  exit 1
fi
