#!/usr/bin/env bash
# Fabelo Studio — one-time setup in a fresh workspace (Linux). Safe to re-run.
# Installs: Python audio deps, Kokoro TTS models (~120 MB, GitHub releases), puppeteer-core, finds Chrome.
set -e
KIT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS="${FABELO_MODELS:-$HOME/tts}"

pip install --quiet --break-system-packages kokoro-onnx soundfile numpy 2>/dev/null || pip install --quiet kokoro-onnx soundfile numpy

mkdir -p "$MODELS"
REL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  [ -s "$MODELS/$f" ] || { echo "downloading $f"; curl -sSL -o "$MODELS/$f" "$REL/$f"; }
done

RT="${FABELO_RT:-/tmp/fabelo-rt}"
mkdir -p "$RT"
[ -d "$RT/node_modules/puppeteer-core" ] || (cd "$RT" && npm init -y >/dev/null && npm i --silent puppeteer-core)

CHROME="${CHROME_PATH:-}"
for c in "$CHROME" /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser $(ls -d $HOME/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null); do
  [ -n "$c" ] && [ -x "$c" ] && CHROME="$c" && break
done
if [ -z "$CHROME" ] || [ ! -x "$CHROME" ]; then
  pip install --quiet --break-system-packages playwright 2>/dev/null || true
  python3 -m playwright install chromium >/dev/null 2>&1 || true
  CHROME=$(ls -d $HOME/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1)
fi
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg missing (apt-get install -y ffmpeg)"

cat > "$KIT/.env.sh" <<EOF
export FABELO_KIT="$KIT"
export FABELO_MODELS="$MODELS"
export NODE_PATH="$RT/node_modules"
export CHROME_PATH="$CHROME"
EOF
echo "ready. run:  source $KIT/.env.sh"
echo "  models: $MODELS   chrome: $CHROME"
