#!/usr/bin/env python3
"""Build the deterministic standalone Studio from reviewed, inert local sources."""
from pathlib import Path
import argparse
root = Path(__file__).resolve().parents[1]
shell = (root/'web/studio-shell.html').read_text()
for marker, filename in [('/*STUDIO_CORE*/','studio-core.js'),('/*STUDIO_APP*/','studio-app.js')]:
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
