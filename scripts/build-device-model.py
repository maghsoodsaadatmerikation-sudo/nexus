#!/usr/bin/env python3
"""Package reviewed local model runtime; weights are never put in Git or the static site."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def artifacts():
    source=ROOT/'web/device'
    raw=(source/'model-manifest.json').read_bytes();manifest=json.loads(raw)
    assert manifest['schema']=='nexus.device-model.v1'
    assert len(manifest['revision'])==40 and manifest['download_bytes']==sum(x['bytes'] for x in manifest['assets'])
    assert manifest['download_bytes']<180000000
    files={'model-manifest.json':raw,'device-engine.js':(source/'device-engine.js').read_bytes(),
           'device-worker.js':(source/'device-worker.js').read_text().replace('__MANIFEST_SHA__',hashlib.sha256(raw).hexdigest()).encode()}
    for name,digest in manifest['vendor'].items():
        content=(source/'vendor'/name).read_bytes();assert hashlib.sha256(content).hexdigest()==digest,name
        files['vendor/'+name]=content
    return files

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    for name,content in artifacts().items():
        path=ROOT/'public/studio/device'/name
        if args.check:
            assert path.is_file() and path.read_bytes()==content,'stale device artifact: '+name
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    print('DEVICE MODEL PACKAGE: PASS')
if __name__=='__main__':main()
