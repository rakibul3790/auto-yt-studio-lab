#!/usr/bin/env python3
"""
Smooth Scribble (s2): turn a scene source into ONE self-contained HTML file for record2.js.

Inlines s2/lib/scribble2.js, s2/lib/sets2.js, the Caveat font (__CAVEAT__) and the voice timing
(__TIMING_JSON__, from emo_voice.py) so the page renders anywhere, locally or in the cloud.

  python3 s2/tools/build_s2.py work/<slug>/film.src.html work/<slug>/film.html --timing work/<slug>/voice/timing.json
"""
import argparse, json, os, re

S2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.dirname(S2)
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--timing")
a = ap.parse_args()
html = open(a.src, encoding="utf-8").read()
read = lambda *p: open(os.path.join(*p), encoding="utf-8").read()
inline = lambda code: lambda m: "<script>\n" + code.replace("</script", "<\\/script") + "\n</script>"
html = re.sub(r'<script src="[^"]*scribble2\.js"></script>', inline(read(S2, "lib", "scribble2.js")), html)
html = re.sub(r'<script src="[^"]*sets2\.js"></script>', inline(read(S2, "lib", "sets2.js")), html)
html = html.replace("__CAVEAT__", read(KIT, "lib", "caveat700.b64").strip())
timing = "null"
if a.timing and os.path.exists(a.timing):
    timing = json.dumps(json.load(open(a.timing, encoding="utf-8")), separators=(",", ":")).replace("</", "<\\/")
html = html.replace("__TIMING_JSON__", timing)
left = [p for p in ('scribble2.js"', 'sets2.js"') if p in html]
assert not left, f"build failed, still in the file: {left}"
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, "w", encoding="utf-8").write(html)
print(f"built {a.out} ({len(html) / 1024:.0f} KB){'' if timing != 'null' else '  (no timing)'}")
