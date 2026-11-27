# Fabelo Studio v2 renders

One folder per film: `film.src.html` + `film.audio.json` (+ optional `FINISH` with finish.py options).
Add a `RENDER` file holding the record options (for example `--w 1080 --h 1920 --fps 30 --blur 4`)
and push to a branch named `fabelo-v2-render-<slug>`. The workflow **Render Fabelo v2 film**
runs the whole pipeline in the cloud and commits back `final.mp4`, `timing.json`, `finish.json` and `qc/`.
It never uploads anything to YouTube.
