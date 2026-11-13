#!/usr/bin/env python3
"""Embed complete reviewed language catalogs and pin the standalone app shell."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def build(check=False):
    packs={k:json.loads((ROOT/f'web/locales/{k}.json').read_text()) for k in ('en','fa')}
    en=packs['en'];keys=set(en['messages'])
    digest=hashlib.sha256(json.dumps(en['messages'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    assert len(keys)>=277 and keys=={f'm{i:03}' for i in range(len(keys))}
    for code,pack in packs.items():
        assert pack['schema']=='nexus.ui-language.v1' and pack['locale']==code
        assert pack['source_sha256']==digest and set(pack['messages'])==keys
        assert pack['direction']==('rtl' if code=='fa' else 'ltr')
        assert all(isinstance(v,str) and v.strip() for v in pack['messages'].values())
    page=ROOT/'web/offline-pilot.html';original=page.read_text();initial=original
    payload=json.dumps(packs,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    original=re.sub(r'(<meta name="nexus-ui-messages" content=")[0-9]+(")',lambda m:m[1]+str(len(keys))+m[2],original)
    updated,n=re.subn(r'/\* NEXUS_LOCALES_BEGIN \*/.*?/\* NEXUS_LOCALES_END \*/',lambda _: '/* NEXUS_LOCALES_BEGIN */'+payload+'/* NEXUS_LOCALES_END */',original,flags=re.S)
    assert n==1
    core=(ROOT/'web/table-core.js').read_text().rstrip()+'\n'+(ROOT/'web/data-analysis-core.js').read_text().rstrip()
    updated,core_count=re.subn(
        r'/\* NEXUS_DATA_ANALYSIS_BEGIN \*/.*?/\* NEXUS_DATA_ANALYSIS_END \*/',
        lambda _:'/* NEXUS_DATA_ANALYSIS_BEGIN */\n'+core+'\n/* NEXUS_DATA_ANALYSIS_END */',
        updated,flags=re.S)
    assert core_count==1
    search_core=(ROOT/'web/web-research-core.js').read_text().rstrip()
    updated,search_count=re.subn(
        r'/\* NEXUS_WEB_RESEARCH_BEGIN \*/.*?/\* NEXUS_WEB_RESEARCH_END \*/',
        lambda _:'/* NEXUS_WEB_RESEARCH_BEGIN */\n'+search_core+'\n  /* NEXUS_WEB_RESEARCH_END */',
        updated,flags=re.S)
    assert search_count==1
    chat_core=(ROOT/'web/guided-chat-core.js').read_text().rstrip()
    updated,chat_count=re.subn(
        r'/\* NEXUS_GUIDED_CHAT_BEGIN \*/.*?/\* NEXUS_GUIDED_CHAT_END \*/',
        lambda _:'/* NEXUS_GUIDED_CHAT_BEGIN */\n'+chat_core+'\n  /* NEXUS_GUIDED_CHAT_END */',
        updated,flags=re.S)
    assert chat_count==1 and len(updated.encode())<300000
    digest=hashlib.sha256(updated.encode()).hexdigest()
    worker=ROOT/'public/service-worker.js';old_worker=worker.read_text()
    new_worker,n=re.subn(r"const EXPECTED_SHA256='[a-f0-9]{64}'",f"const EXPECTED_SHA256='{digest}'",old_worker)
    assert n==1
    if check:assert updated==initial and new_worker==old_worker,'stale embedded catalog or worker hash'
    else:page.write_text(updated);worker.write_text(new_worker)
    print(json.dumps({'status':'PASS','complete_messages_per_language':len(keys),'languages':list(packs),'app_bytes':len(updated.encode()),'check_only':check}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');build(p.parse_args().check)
