#!/usr/bin/env python3
"""Build the deterministic standalone Studio from reviewed, inert local sources."""
from pathlib import Path
import argparse
import hashlib
from studio_module_graph import validate_module_graph
from studio_template_contract import replace_exact
root = Path(__file__).resolve().parents[1]
vendor=root/'web/vendor/astronomy-2.1.19.min.js'
if hashlib.sha256(vendor.read_bytes()).hexdigest()!='f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6':
    raise ValueError('vendored ephemeris hash mismatch')
shell = (root/'web/studio-shell.html').read_text()
theme = (root/'web/studio-theme.css').read_text()
if '</style' in theme.lower() or shell.count('/*STUDIO_THEME*/') != 1:
    raise ValueError('invalid Studio theme source')
modules = validate_module_graph(shell, root/'web')
shell = replace_exact(shell, '/*STUDIO_THEME*/', theme)
for item in modules:
    marker, filename = item.marker, item.filename
    code = (root/'web'/filename).read_text()
    if '</script' in code.lower():
        raise ValueError('script closing sequence is not permitted in bundled sources')
    shell = replace_exact(shell, marker, code)
cli=argparse.ArgumentParser();cli.add_argument('--check',action='store_true');args=cli.parse_args()
out=root/'web/studio.html'
if args.check:
    if not out.exists() or out.read_text()!=shell:raise SystemExit('Studio bundle is stale')
else:out.write_text(shell)
