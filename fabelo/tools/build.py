#!/usr/bin/env python3
"""
Turn a scene source (scene.src.html) into ONE self-contained HTML file:
inlines lib/scribble.js and the embedded Caveat font (__CAVEAT__ placeholder).
The result opens anywhere, publishes as an artifact, and records offline.

  python tools/build.py work/film.src.html work/film.html
"""
import os, re, sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src, out = sys.argv[1], sys.argv[2]
html = open(src, encoding="utf-8").read()
lib = open(os.path.join(KIT, "lib", "scribble.js"), encoding="utf-8").read()
font = open(os.path.join(KIT, "lib", "caveat700.b64"), encoding="utf-8").read().strip()
html = re.sub(r'<script src="[^"]*scribble\.js"></script>', lambda m: "<script>\n" + lib + "\n</script>", html)
html = html.replace("__CAVEAT__", font)
assert "__CAVEAT__" not in html and "scribble.js\"" not in html, "build failed: placeholder left"
open(out, "w", encoding="utf-8").write(html)
print(f"built {out} ({len(html) / 1024:.0f} KB)")
