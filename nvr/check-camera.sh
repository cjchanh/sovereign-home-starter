#!/usr/bin/env bash
# Quick RTSP reachability check — confirm a camera's stream + credentials BEFORE
# wiring it into Frigate, so you debug one thing at a time. Needs ffmpeg (ffprobe).
#
# Usage:
#   ./check-camera.sh 'rtsp://user:pass@192.168.1.50:554/stream2'
set -euo pipefail

url="${1:-}"
if [ -z "$url" ]; then
  echo "usage: $0 'rtsp://user:pass@CAMERA_IP:554/stream'"
  echo "  Tapo:    rtsp://user:pass@IP:554/stream1 (HD) or /stream2 (SD)"
  echo "  Reolink: rtsp://user:pass@IP:554/h264Preview_01_main (or _sub)"
  exit 2
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe not found — install ffmpeg first (e.g. sudo apt install ffmpeg)."
  exit 3
fi

echo "probing $url ..."
if ffprobe -v error -rtsp_transport tcp -timeout 5000000 \
     -show_entries stream=codec_name,width,height \
     -of default=noprint_wrappers=1 "$url"; then
  echo "OK — stream reachable. Use this exact URL in nvr/config.yml."
else
  echo "FAILED — check the IP, the credentials (letters + digits only — Frigate"
  echo "         doesn't URL-encode the password), and that RTSP is enabled."
  exit 1
fi
