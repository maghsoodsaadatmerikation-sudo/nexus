#!/usr/bin/env python3
"""Read-only, fixed-origin identity of the separately hosted static Studio."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_assets',ROOT/'scripts/verify-public-pwa-assets.py')
observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
observer.ORIGIN='https://nexus-studio-merikation.onrender.com'
observer.ASSETS={
    '/':('public/studio/index.html','text/html'),
    '/manifest.json':('public/studio/manifest.json','manifest'),
    '/service-worker.js':('public/studio/service-worker.js','javascript'),
    '/icons/nexus-192.png':('public/studio/icons/nexus-192.png','image/png'),
    '/icons/nexus-512.png':('public/studio/icons/nexus-512.png','image/png'),
}


def sanity():
    subprocess.run([sys.executable,str(ROOT/'scripts/build-studio-static.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    html=(ROOT/'public/studio/index.html').read_bytes()
    worker=(ROOT/'public/studio/service-worker.js').read_text()
    manifest=json.loads((ROOT/'public/studio/manifest.json').read_text())
    assert "const EXPECTED_SHA256='"+hashlib.sha256(html).hexdigest()+"'" in worker
    assert manifest['scope']==manifest['start_url']=='./'
    assert manifest['display']=='standalone'
    assert b"manifest-src 'self'" in html and b"worker-src 'self' blob:" in html
    assert b'id="studio-offline"' in html and b'No model hosted here' in html
    assert {icon['src'] for icon in manifest['icons']}=={'./icons/nexus-192.png','./icons/nexus-512.png'}


observer.source_sanity=sanity
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--self-test',action='store_true');parser.add_argument('--attempts',type=int,default=1);args=parser.parse_args()
    if args.self_test:observer.self_test()
    else:
        report=observer.public_observation(args.attempts)
        report['schema']='nexus.studio.public-assets.v1'
        print(json.dumps(report,sort_keys=True))
        if report['status']!='PASS':raise SystemExit(1)
