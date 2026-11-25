#!/usr/bin/env python3
"""Build the deterministic standalone Studio from reviewed, inert local sources."""
from pathlib import Path
import argparse
import base64
import hashlib
from textwrap import dedent
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
brand = base64.b64encode((root/'web/nexus-brand-icon.png').read_bytes()).decode('ascii')
shell = replace_exact(shell, '__NEXUS_BRAND_PNG__', brand)
for item in modules:
    marker, filename = item.marker, item.filename
    code = (root/'web'/filename).read_text()
    if filename == 'studio-office-zip.js':
        # Reuse the static offline file desk ZIP and XML helpers. The pilot keeps its
        # reviewed bytes while Studio supplies its own smaller expansion limit.
        pilot = (root/'web/offline-pilot.html').read_text()
        start = pilot.index('  function decodeFileText(bytes){')
        helpers = pilot.index('  const xmlElements=', start)
        crc = pilot.index('  const ZIP_CRC_TABLE=', helpers)
        end = pilot.index('  async function officeText(', crc)
        reader = dedent(pilot[start:helpers]) + dedent(pilot[crc:end])
        writer_start = pilot.index('  function makeZip(entries){')
        writer_end = pilot.index('  function reportRows(raw){', writer_start)
        writer = dedent(pilot[writer_start:writer_end])
        code = replace_exact(code, '/* OFFICE_ZIP_HELPERS */', (reader + writer).rstrip())
    if filename == 'studio-app.js':
        # One reviewed engine in an immutable lexical closure, shared with
        # the later composer. No new window export or dynamic module loader.
        import re
        review_source = []
        for name in ["studio-workflow-critique.mjs", "studio-workflow-recovery.mjs", "studio-workflow-outcome.mjs", "studio-workflow-review.mjs", "studio-experience-archive-edit.mjs", "studio-chat-experience-report.mjs", "studio-experience-archive-recall.mjs", "studio-chat-correction-options.mjs"]:
            part = (root/'web'/name).read_text()
            part = re.sub(r'^import[^\n]*\n', '', part, flags=re.M)
            part = re.sub(r'^export function ', 'function ', part, flags=re.M)
            if re.search(r'^\s*(import|export)\s', part, re.M):
                raise ValueError('unsupported review module syntax')
            # Preserve line boundaries (including ASI). Only strip standalone
            # line comments in this narrow reviewed module subset, never in
            # template literals, multiline strings or block comments.
            if not any(token in part for token in ("`", "/*", "\\\n")):
                part = re.sub(r'^[ \t]*//[^\n]*$', '', part, flags=re.M)
            review_source.append(part)
        code = replace_exact(code, '/* EXPERIENCE_EDIT_ENGINE */', '\n'.join(review_source))
    if '</script' in code.lower():
        raise ValueError('script closing sequence is not permitted in bundled sources')
    shell = replace_exact(shell, marker, code)
cli=argparse.ArgumentParser();cli.add_argument('--check',action='store_true');args=cli.parse_args()
out=root/'web/studio.html'
if args.check:
    if not out.exists() or out.read_text()!=shell:raise SystemExit('Studio bundle is stale')
else:out.write_text(shell)
