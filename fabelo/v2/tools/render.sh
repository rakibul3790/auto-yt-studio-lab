#!/usr/bin/env bash
# Fabelo Studio v2: the whole pipeline for one film folder, in order.
#
#   bash v2/tools/render.sh <dir> [record options]       e.g.  bash v2/tools/render.sh v2/renders/plane --w 1080 --h 1920 --fps 30 --blur 4
#
# <dir> holds film.src.html and film.audio.json. Optional <dir>/FINISH holds finish.py options (e.g. --grade warm --size 2160x3840).
# Steps: voices (real line lengths + word times) → build → record (motion blur) → mix → finish (grade, grain, -14 LUFS) → QC.
# Writes <dir>/final.mp4, <dir>/timing.json, <dir>/finish.json, <dir>/qc/ (frames, sheets, report). Scratch files go in <dir>/work/.
set -euo pipefail
D="${1:?usage: render.sh <dir> [record options]}"; shift
V2="$(cd "$(dirname "$0")/.." && pwd)"
# Smooth Scribble films (scene uses scribble2.js) go through the s2 pipeline instead.
if grep -q 'scribble2\.js' "$D/film.src.html" 2>/dev/null; then exec bash "$V2/../s2/tools/render_s2.sh" "$D" "$@"; fi
W="$D/work"; mkdir -p "$W"
: "${FABELO_MODELS:?set FABELO_MODELS (run tools/setup.sh, then source .env.sh)}"

echo "== 1/6 voices";  python3 "$V2/tools/voices.py" --spec "$D/film.audio.json" --models "$FABELO_MODELS" --out "$W/voice"
cp "$W/voice/timing.json" "$D/timing.json"
echo "== 2/6 build";   python3 "$V2/tools/build2.py" "$D/film.src.html" "$D/film.html" --timing "$W/voice/timing.json"
echo "== 3/6 record";  node "$V2/tools/record2.js" "$D/film.html" "$W/master.mp4" --cues "$W/cues.json" "$@"
echo "== 4/6 mix";     python3 "$V2/tools/mix.py" --spec "$D/film.audio.json" --voice "$W/voice" --cues "$W/cues.json" --out "$W/mix.wav" --stems
echo "== 5/6 finish";  python3 "$V2/tools/finish.py" --video "$W/master.mp4" --audio "$W/mix.wav" --out "$D/final.mp4" --report "$D/finish.json" $( [ -f "$D/FINISH" ] && cat "$D/FINISH" )
echo "== 6/6 qc";      node "$V2/tools/qc.js" "$D/film.html" "$D/qc" --video "$D/final.mp4" || echo "QC found problems: see $D/qc/report.md"
echo "done → $D/final.mp4"
