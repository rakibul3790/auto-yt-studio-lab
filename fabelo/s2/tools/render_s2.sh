#!/usr/bin/env bash
# Smooth Scribble (s2): the whole pipeline for one film folder.
#
#   bash s2/tools/render_s2.sh <dir> [record options]      e.g.  bash s2/tools/render_s2.sh work/meet --w 1920 --h 1080 --fps 30 --blur 2
#
# <dir> holds film.src.html and film.audio.json (voices + emotional lines + sfx/beds/music).
#   <dir>/voice/timing.json present  → those voice files are used as they are (e.g. ElevenLabs v3 takes), no Kokoro run.
#   "sfx_files" in film.audio.json   → real effect files from <dir>/sfx/ are laid over the mix (s2/tools/overlay_files.py).
#   <dir>/FINISH                      → finish.py options (default: --grade warm --paper 0.05 --grain 0.25 --vignette 0.25).
# Steps: voices → build → record (v2 recorder, motion blur) → mix (v2) [+ effect files] → finish (v2, -14 LUFS) → QC sheets.
# The cloud workflow "Render Fabelo v2 film" reaches this through v2/tools/render.sh when film.src.html uses scribble2.js.
# Set PYTHON=python if python3 is not the interpreter with numpy/soundfile (Windows).
# Writes <dir>/final.mp4, <dir>/timing.json, <dir>/finish.json, <dir>/qc/sheet_*.jpg; scratch in <dir>/work/.
set -euo pipefail
D="${1:?usage: render_s2.sh <dir> [record options]}"; shift
PY="${PYTHON:-python3}"
S2="$(cd "$(dirname "$0")/.." && pwd)"; V2="$S2/../v2"
W="$D/work"; mkdir -p "$W"
if [ -f "$D/voice/timing.json" ]; then
  echo "== 1/6 voices: using the prepared voice files in $D/voice"
  rm -rf "$W/voice"; cp -r "$D/voice" "$W/voice"
else
  : "${FABELO_MODELS:?set FABELO_MODELS (run tools/setup.sh, then source .env.sh)}"
  echo "== 1/6 voices (free Kokoro, emotion shaped)"; "$PY" "$S2/tools/emo_voice.py" --spec "$D/film.audio.json" --models "$FABELO_MODELS" --out "$W/voice"
fi
cp "$W/voice/timing.json" "$D/timing.json"
echo "== 2/6 build";  "$PY" "$S2/tools/build_s2.py" "$D/film.src.html" "$D/film.html" --timing "$W/voice/timing.json"
echo "== 3/6 record"; node "$V2/tools/record2.js" "$D/film.html" "$W/master.mp4" ${CHROME_PATH:+--chrome "$CHROME_PATH"} "$@"
echo "== 4/6 mix";    "$PY" "$V2/tools/mix.py" --spec "$D/film.audio.json" --voice "$W/voice" --out "$W/mix.wav"
MIX="$W/mix.wav"
if grep -q '"sfx_files"' "$D/film.audio.json"; then
  "$PY" "$S2/tools/overlay_files.py" --spec "$D/film.audio.json" --dir "$D" --mix "$W/mix.wav" --out "$W/mix_sfx.wav"; MIX="$W/mix_sfx.wav"
fi
echo "== 5/6 finish"
ffmpeg -y -v error -i "$MIX" -af "loudnorm=I=-14:TP=-2:LRA=11,aresample=48000" -ar 48000 "$W/mix_n.wav"
FIN="--grade warm --paper 0.05 --grain 0.25 --vignette 0.25"; [ -f "$D/FINISH" ] && FIN="$(cat "$D/FINISH")"
"$PY" "$V2/tools/finish.py" --video "$W/master.mp4" --audio "$W/mix_n.wav" --out "$D/final.mp4" --report "$D/finish.json" $FIN
echo "== 6/6 qc sheets (2 fps)"
mkdir -p "$D/qc"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$D/final.mp4")
ffmpeg -y -v error -i "$D/final.mp4" -vf "fps=2,scale=216:-1,tile=10x6" -frames:v 1 "$D/qc/sheet_0-30s.jpg"
ffmpeg -y -v error -ss 30 -i "$D/final.mp4" -vf "fps=2,scale=216:-1,tile=10x6" -frames:v 1 "$D/qc/sheet_30s-end.jpg" || true
{ echo "## Smooth Scribble render: $(basename "$D")"; echo; echo "- duration: ${DUR}s"; echo "- QC sheets: qc/sheet_0-30s.jpg, qc/sheet_30s-end.jpg (2 fps)"; echo; echo '```'; cat "$D/finish.json"; echo; echo '```'; } > "$D/qc/report.md"   # the cloud workflow prints this into the run summary
echo "done → $D/final.mp4  (${DUR}s)"
