#!/usr/bin/env python3
"""Build the deterministic standalone Studio from reviewed, inert local sources."""
from pathlib import Path
import argparse
import hashlib
root = Path(__file__).resolve().parents[1]
vendor=root/'web/vendor/astronomy-2.1.19.min.js'
if hashlib.sha256(vendor.read_bytes()).hexdigest()!='f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6':
    raise ValueError('vendored ephemeris hash mismatch')
shell = (root/'web/studio-shell.html').read_text()
for marker, filename in [('/*STUDIO_ASTRONOMY_VENDOR*/','vendor/astronomy-2.1.19.min.js'),('/*STUDIO_ASTROLOGY*/','studio-astrology.js'),('/*STUDIO_SKY*/','studio-sky.js'),('/*STUDIO_CORE*/','studio-core.js'),('/*STUDIO_LAB*/','studio-lab.js'),('/*STUDIO_APP*/','studio-app.js'),('/*STUDIO_LAB_UI*/','studio-lab-ui.js'),('/*STUDIO_ASTROLOGY_UI*/','studio-astrology-ui.js'),('/*STUDIO_SKY_UI*/','studio-sky-ui.js')]:
    code = (root/'web'/filename).read_text()
    if '</script' in code.lower():
        raise ValueError('script closing sequence is not permitted in bundled sources')
    assert shell.count(marker)==1
    shell = shell.replace(marker,code)
cli=argparse.ArgumentParser();cli.add_argument('--check',action='store_true');args=cli.parse_args()
out=root/'web/studio.html'
if args.check:
    if not out.exists() or out.read_text()!=shell:raise SystemExit('Studio bundle is stale')
else:out.write_text(shell)
