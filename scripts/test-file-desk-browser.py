#!/usr/bin/env python3
"""Disposable real-browser acceptance: local file desk and independently validated document packages."""
import json
import base64
import csv
import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const tick=()=>new Promise(r=>setTimeout(r,30));
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await tick()}throw Error('file-wait-expired')};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 let consent=true,prompts=0,downloads=[],network=0,prints=0;
 window.confirm=()=>{prompts++;return consent};window.print=()=>prints++;
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 const nativeCreate=URL.createObjectURL,urls=new Map();
 URL.createObjectURL=b=>{const url=nativeCreate(b);urls.set(url,b);return url};
 HTMLAnchorElement.prototype.click=function(){downloads.push({name:this.download,blob:urls.get(this.href)})};
 const fixtures={"docx": "UEsDBBQAAAAIAMqIbF34NITmogAAAMoAAAARAAAAd29yZC9kb2N1bWVudC54bWyzsa/IzVEoSy0qzszPs1Uy1DNQsrezKbdKyU8uzU3NK1EASucVW5XbKmWUlBRY6esXJ2ek5iYW6+UXpOYB5dLyi3ITS4DconT98vyilIKi/OTU4uLMvPTcHH0jAwMz/dzEzDwlkJFJ+SmVILoARBSBiBI75/zcgiKg+tQUBbiNNxtvLL+x8cbm2z0KH+bPaLDRBykEkUVgsgBMQgzTRzjUDgBQSwECFAMUAAAACADKiGxd+DSE5qIAAADKAAAAEQAAAAAAAAAAAAAAgAEAAAAAd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAEAAQA/AAAA0QAAAAAA", "xlsx": "UEsDBBQAAAAIAMqIbF3fmEvcawAAAG4AAAAUAAAAeGwvc2hhcmVkU3RyaW5ncy54bWyzKS4uUajIzckrtlXKKCkpsNLXL07OSM1NLNbLL0jNA8qk5RflJpYAuUXp+sUFRamJKcUZqakluTn6RgYGZvq5iZl5SnY2xZl2NiV2wRmJRakpCjcbbyy/sfHG5ts9Nvoldjb6IEl9oEV2AFBLAwQUAAAACADKiGxdgBYZSrkAAAAKAQAAGAAAAHhsL3dvcmtzaGVldHMvc2hlZXQxLnhtbE1PSwrCMBC9SshKQZy2ggtJA4pbV8UDhJraYD4lGVpv4A28hXsPJJ7DpEpx9z7z5s2wwflLaKVEcjXahpK2iN0GINStNCIsXSdtdBrnjcBI/RlC56U4jSGjociyNRihLOVs1PYCBWfeDcSXNI9qncA2pwRLGiLvecag5wzqn7f7espqZWWFPs6owBny1/Pxvt9ILbVmgDGR5BSDuH7qKKaOhBpeHQ+zfFHMGTSpbDWVfVPwdyVM7/MPUEsBAhQDFAAAAAgAyohsXd+YS9xrAAAAbgAAABQAAAAAAAAAAAAAAIABAAAAAHhsL3NoYXJlZFN0cmluZ3MueG1sUEsBAhQDFAAAAAgAyohsXYAWGUq5AAAACgEAABgAAAAAAAAAAAAAAIABnQAAAHhsL3dvcmtzaGVldHMvc2hlZXQxLnhtbFBLBQYAAAAAAgACAIgAAACMAQAAAAA=", "pptx": "UEsDBBQAAAAIAMqIbF18JbyCVQAAAGoAAAAVAAAAcHB0L3NsaWRlcy9zbGlkZTEueG1ssymwKs5JUajIzckrtiqwVSotygMKZKakKkHFEiFiKUWJ5Zl56Up2NgVWycE5KXY2iVYldsEglQolqRUlCjcbbyy/sfHG5ts9NvogKRt9mEJ9sBV2AFBLAQIUAxQAAAAIAMqIbF18JbyCVQAAAGoAAAAVAAAAAAAAAAAAAACAAQAAAABwcHQvc2xpZGVzL3NsaWRlMS54bWxQSwUGAAAAAAEAAQBDAAAAiAAAAAAA", "dtd": "UEsDBBQAAAAIAMqIbF0BwMIhqQAAANkAAAARAAAAd29yZC9kb2N1bWVudC54bWxFjrkOwjAQRH/FcUFnHFFQhOAGUlBwSHETIQqTOIfkS/aihL/HhoLmzV6zmjI7Xg+8uVVoQfcyqy78xBskF0B1U/PqjHA/KVlQSo0FIoiXQhGQAUiaY/Zg5Vx0tn1paQAtWplQzHs8ArhoCu0otQhr66SJu956LSC2fqCz9Z3ztpUhTGbQim7yfEu1mAxOL5+2eyd1CT4B2CrG2pU0lYn+S/fl75z+o7APUEsBAhQDFAAAAAgAyohsXQHAwiGpAAAA2QAAABEAAAAAAAAAAAAAAIABAAAAAHdvcmQvZG9jdW1lbnQueG1sUEsFBgAAAAABAAEAPwAAANgAAAAAAA==", "crc": "UEsDBBQAAAAIAMqIbF34NITmogAAAMoAAAARAAAAd29yZC9kb2N1bWVudC54bWyzsa/IzVEoSy0qzszPs1Uy1DNQsrezKbdKyU8uzU3NK1EASucVW5XbKmWUlBRY6esXJ2ek5iYW6+UXpOYB5dLyi3ITS4DconT98vyilIKi/OTU4uLMvPTcHH0jAwMz/dzEzDwlkJFJ+SmVILoARBSBiBI75/zcgiKg+tQUBbiNNxtvLL+x8cbm2z0KH+bPaLDRBykEkUVgsgBMQgzTRzjUDgBQSwECFAMUAAAACADKiGxd+TSE5qIAAADKAAAAEQAAAAAAAAAAAAAAgAEAAAAAd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAEAAQA/AAAA0QAAAAAA", "bomb": "UEsDBBQAAAAIAMqIbF34NITmogAAAMoAAAARAAAAd29yZC9kb2N1bWVudC54bWyzsa/IzVEoSy0qzszPs1Uy1DNQsrezKbdKyU8uzU3NK1EASucVW5XbKmWUlBRY6esXJ2ek5iYW6+UXpOYB5dLyi3ITS4DconT98vyilIKi/OTU4uLMvPTcHH0jAwMz/dzEzDwlkJFJ+SmVILoARBSBiBI75/zcgiKg+tQUBbiNNxtvLL+x8cbm2z0KH+bPaLDRBykEkUVgsgBMQgzTRzjUDgBQSwECFAMUAAAACADKiGxd+DSE5qIAAAAAAABAEQAAAAAAAAAAAAAAgAEAAAAAd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAEAAQA/AAAA0QAAAAAA", "traversal": "UEsDBBQAAAAIAMqIbF0rhCYSBgAAAAQAAAAUAAAALi4vd29yZC9kb2N1bWVudC54bWyzqdC3AwBQSwECFAMUAAAACADKiGxdK4QmEgYAAAAEAAAAFAAAAAAAAAAAAAAAgAEAAAAALi4vd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAEAAQBCAAAAOAAAAAAA"};
 const decode=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
 const rows=()=>Array.from($('files-list').querySelectorAll('.entry'));
 const row=name=>rows().find(r=>r.querySelector('b').textContent===name);
 const add=async files=>{const dt=new DataTransfer();for(const f of files)dt.items.add(f);$('files-input').files=dt.files;$('files-input').dispatchEvent(new Event('change'));await wait(()=>!$('files-add').disabled&&$('files-input').value==='')};
 const preview=async name=>{row(name).querySelectorAll('button')[0].click();await wait(()=>$('files-state').textContent.includes('preview ready')||$('files-state').textContent.includes('unavailable'))};
 const snapshot=async()=>{const n=downloads.length;$('export').click();if(downloads.length!==n+1)throw Error('json-export-missing');return await downloads.at(-1).blob.text()};
 const artifacts={};
 try{
  assert(rows().length===0&&$('files-claim').disabled===true,'empty-file-desk-does-not-open-or-read-files');
  const textName='../<img src=x>.txt',text='=HYPERLINK("https://example.invalid") <img src=x> فارسی 😀';
  await add([new File([text],textName,{type:'text/plain'}),new File([Uint8Array.of(0,1,2,255)],'original.bin',{type:'application/octet-stream'}),new File(['%PDF synthetic'],'sample.pdf',{type:'application/pdf'})]);
  assert(rows().length===3&&!$('draft-notice').hidden&&$('question').value==='','any-type-file-selection-is-local-and-not-a-workspace-event');
  assert(!document.querySelector('#files-list img')&&row(textName).querySelector('code').textContent.length===64,'filenames-are-inert-and-byte-identities-are-visible');
  consent=false;const p=prompts;$('new').click();
  assert(prompts===p+1&&rows().length===3,'first-file-tray-is-protected-before-new-workspace');
  const imported={schema:'nexus.offline-pilot.v1',authority:'none',storage:'memory_only',workspace:{id:'offline-test-import-files',question:'Other workspace',goal:'',constraints:[],values:[],claims:[],alternatives:[],judgment:null},events:[{sequence:1,kind:'question',at:'2026-11-12T00:00:00.000Z'}]};
  const dt=new DataTransfer();dt.items.add(new File([JSON.stringify(imported)],'workspace.json',{type:'application/json'}));$('file').files=dt.files;$('file').dispatchEvent(new Event('change'));await wait(()=>$('file').value==='');
  assert(rows().length===3&&$('question').value==='','cancelled-import-preserves-a-tray-without-committed-events');
  const beforeOriginal=downloads.length;row('original.bin').querySelectorAll('button')[1].click();
  assert(downloads.length===beforeOriginal,'original-download-requires-confirmation');
  consent=true;row('original.bin').querySelectorAll('button')[1].click();
  assert(Array.from(new Uint8Array(await downloads.at(-1).blob.arrayBuffer())).join(',')==='0,1,2,255','original-download-preserves-binary-bytes');
  await preview('sample.pdf');assert($('files-preview').value===''&&rows().length===3,'unsupported-pdf-is-not-pretended-to-be-read-and-original-is-retained');
  await preview(textName);
  assert($('files-preview').value===text&&!$('files-preview').querySelector('img'),'utf8-text-and-markup-preview-are-inert');
  $('files-claim').click();
  assert($('claim').value===text&&$('source').value.startsWith('local-file:sha256:')&&$('origin').value==='external_evidence'&&$('claims').textContent.includes('No evidence'),'file-excerpt-enters-only-an-unregistered-source-labelled-draft');
  const question='=2+2 <script>alert(1)</script> فارسی 😀';fill('question',question);fill('goal','Human-owned synthetic report');submit('ask-form');const beforeClaim=await snapshot();
  consent=false;fill('claim','existing draft');$('files-claim').click();
  assert($('claim').value==='existing draft','cancelled-excerpt-replacement-preserves-existing-draft');
  consent=true;$('files-claim').click();
  assert(await snapshot()===beforeClaim,'preview-and-excerpt-do-not-mutate-workspace-history');
  submit('claim-form');const committed=await snapshot();fill('export-passphrase','NEVER_EXPORT_FILE_SECRET');
  await add(['docx','xlsx','pptx'].map(k=>new File([decode(fixtures[k])],'compressed.'+k,{type:'application/octet-stream'})));
  await preview('compressed.docx');assert($('files-preview').value.includes('Compressed document فارسی 😀'),'bounded-deflated-docx-body-text-is-extracted');
  await preview('compressed.xlsx');assert($('files-preview').value.includes('Shared فارسی')&&$('files-preview').value.includes('中文 cell')&&$('files-preview').value.includes('not evaluated'),'xlsx-strings-are-read-and-formulas-are-not-calculated');
  await preview('compressed.pptx');assert($('files-preview').value.includes('Slide text فارسی'),'pptx-slide-text-is-extracted-without-running-content');
  await add(['dtd','crc','bomb','traversal'].map(k=>new File([decode(fixtures[k])],k+'.docx')));
  for(const k of ['dtd','crc','bomb','traversal']){await preview(k+'.docx');if(!$('files-state').textContent.includes('unavailable')||$('files-preview').value!=='')throw Error('unsafe-archive-preview-was-accepted')}
  assert(rows().length===10,'dtd-corrupt-inflation-and-traversal-previews-rejected-with-originals-retained');
  const n=rows().length;
  await add([new File([new Uint8Array(10*1024*1024+1)],'oversized.bin')]);
  assert(rows().length===n&&$('files-state').textContent.includes('could not'),'per-file-size-limit-rejects-without-partial-add');
  await add(Array.from({length:21},(_,i)=>new File(['x'],'count-'+i+'.txt')));
  assert(rows().length===n,'file-count-limit-is-atomic');
  const block=new Uint8Array(8*1024*1024);await add([0,1,2].map(i=>new File([block],'total-'+i+'.bin')));
  assert(rows().length===n,'total-byte-budget-rejects-without-discarding-existing-files');
  change('ui-language','fa');assert(rows().length===n&&row(textName)&&$('files-add').textContent==='افزودن فایل به این صفحه','language-change-preserves-files-and-localizes-controls');change('ui-language','en');
  consent=false;const cancelled=downloads.length;$('files-generate').click();
  assert(downloads.length===cancelled,'generated-plaintext-output-requires-confirmation');consent=true;
  for(const format of ['txt','md','csv','html','docx','xlsx','xml','zip']){
    change('files-format',format);const start=downloads.length;$('files-generate').click();
    await wait(()=>!$('files-generate').disabled&&downloads.length===start+1);
    const output=downloads.at(-1),bytes=new Uint8Array(await output.blob.arrayBuffer());
    if(!output.name.endsWith('.'+format)||!bytes.length)throw Error('generated-format-missing');
    let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));artifacts[format]=btoa(binary);
  }
  assert(Object.keys(artifacts).length===8,'eight-real-download-formats-are-produced');
  const html=new DOMParser().parseFromString(new TextDecoder().decode(decode(artifacts.html)),'text/html');
  assert(!html.querySelector('script,img,iframe')&&html.querySelector('pre').textContent.includes(question)&&html.querySelector('meta[http-equiv]').content.includes("default-src 'none'"),'standalone-html-escapes-user-markup-and-blocks-active-resources');
  assert(new TextDecoder().decode(decode(artifacts.md)).includes('&lt;script&gt;')&&!new TextDecoder().decode(decode(artifacts.md)).includes('<script>'),'markdown-does-not-introduce-active-html');
  for(const format of Object.keys(artifacts))if(new TextDecoder().decode(decode(artifacts[format])).includes('NEVER_EXPORT_FILE_SECRET'))throw Error('password-entered-generated-file');
  assert(true,'password-fields-are-excluded-from-every-generated-format');
  change('files-format','pdf');const pdfBefore=downloads.length;$('files-generate').click();
  assert(prints===1&&downloads.length===pdfBefore&&!$('decision-report').hidden,'pdf-uses-explicit-browser-print-instead-of-a-fake-pdf-extension');
  assert(await snapshot()===committed,'file-selection-preview-and-generation-preserve-committed-workspace-and-audit');
  row('original.bin').querySelectorAll('button')[2].click();
  assert(rows().length===n-1&&$('files-preview').value===''&&await snapshot()===committed,'removing-an-original-clears-preview-without-editing-workspace');
  await add([new File([decode(artifacts.docx)],'generated.docx',{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})]);await preview('generated.docx');
  assert($('files-preview').value.includes(question),'generated-word-file-can-be-reopened-as-inert-text');row('generated.docx').querySelectorAll('button')[2].click();
  const nativeBuffer=Blob.prototype.arrayBuffer;let unblock,held=false;
  Blob.prototype.arrayBuffer=async function(){if(!held){held=true;await new Promise(r=>unblock=r)}return nativeBuffer.call(this)};
  change('files-format','zip');const raceDownloads=downloads.length;$('files-generate').click();await wait(()=>!!unblock);
  row('sample.pdf').querySelectorAll('button')[2].click();unblock();await wait(()=>!$('files-generate').disabled);Blob.prototype.arrayBuffer=nativeBuffer;
  assert(downloads.length===raceDownloads&&$('files-state').textContent.includes('could not'),'changed-file-selection-cancels-in-flight-bundle-without-partial-download');
  // Delay a real digest, replace the workspace, and prove late file work cannot attach to it.
  const nativeDigest=crypto.subtle.digest.bind(crypto.subtle);let release,digested=false;
  crypto.subtle.digest=async(...args)=>{await new Promise(r=>release=r);const value=await nativeDigest(...args);digested=true;return value};
  const pending=new DataTransfer();pending.items.add(new File(['late file'],'late.txt'));$('files-input').files=pending.files;$('files-input').dispatchEvent(new Event('change'));await wait(()=>!!release);
  const pendingDownload=downloads.length;$('files-generate').click();assert(downloads.length===pendingDownload,'file-generation-waits-for-pending-file-admission');
  $('new').click();release();await wait(()=>digested);await tick();crypto.subtle.digest=nativeDigest;
  assert(rows().length===0&&!$('files-add').disabled&&$('files-preview').value===''&&$('question').value==='','workspace-replacement-rejects-late-file-read-and-clears-tray');
  assert(network===0&&localStorage.length===0,'file-desk-uses-no-app-network-or-persistent-plaintext-storage');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,network_requests:network,production_verified:false,authority:'none',synthetic_only:true,artifacts});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e.message).replace(/[^a-z-]/g,'')})}
});
"""


def validate_outputs(encoded):
    """Independent stdlib readers, never the app's ZIP/XML implementation."""
    artifacts={k:base64.b64decode(v,validate=True) for k,v in encoded.items()}
    assert set(artifacts)=={'txt','md','csv','html','docx','xlsx','xml','zip'}
    for raw in artifacts.values():
        assert b'NEVER_EXPORT_FILE_SECRET' not in raw
    for kind in ('docx','xlsx','zip'):
        with zipfile.ZipFile(io.BytesIO(artifacts[kind])) as package:
            assert package.testzip() is None
            names=package.namelist()
            assert len(names)==len(set(names)) and all(not p.startswith('/') and '..' not in p.split('/') for p in names)
            if kind=='zip':
                manifest=json.loads(package.read('manifest.json'))
                state=json.loads(package.read('workspace.json'))
                assert manifest['schema']=='nexus.file-bundle.v1' and manifest['authority']=='none'
                assert manifest['originals_included'] and len(manifest['files'])==10
                assert state['authority']=='none' and state['workspace']['judgment'] is None
                assert state['workspace']['question'].startswith('=2+2')
                for item in manifest['files']:
                    data=package.read(item['path'])
                    assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
                    assert item['path'].startswith('attachments/')
                    assert not any(c in item['path'].split('/')[-1] for c in '<>:"|?*')
                assert package.read('attachments/002_original.bin')==bytes([0,1,2,255])
            else:
                assert '[Content_Types].xml' in names and '_rels/.rels' in names
                for name in names:
                    if name.endswith(('.xml','.rels')):ET.fromstring(package.read(name))
                relationships=ET.fromstring(package.read('_rels/.rels'))
                assert all(r.get('TargetMode')!='External' for r in relationships)
                assert all(r.get('Target') in names for r in relationships)
                if kind=='docx':
                    body=ET.fromstring(package.read('word/document.xml'))
                    text=''.join(body.itertext())
                    assert 'فارسی' in text and '<script>' in text and '😀' in text
                    assert body.tag=='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document'
                else:
                    sheet=ET.fromstring(package.read('xl/worksheets/sheet1.xml'))
                    ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                    cells=list(sheet.iter(ns+'c'))
                    assert cells and all(c.get('t')=='inlineStr' for c in cells)
                    assert not list(sheet.iter(ns+'f'))
                    assert '=2+2' in ''.join(sheet.itertext())
    records=list(csv.reader(io.StringIO(artifacts['csv'].decode('utf-8-sig'))))
    assert records and any(cell.startswith("'=2+2") for row in records for cell in row)
    assert all(not cell.lstrip().startswith(('=','+','-','@')) for row in records for cell in row)
    assert 'فارسی' in artifacts['txt'].decode() and '&lt;script&gt;' in artifacts['html'].decode()
    ET.fromstring(artifacts['xml'])
    return {'formats':sorted(artifacts),'independent_zip_crc_and_ooxml_structure':True,'bundle_original_hashes_match':True,'xlsx_contains_no_formulas':True}


def main():
    root = Path(__file__).resolve().parents[1]
    html = (root/'web/offline-pilot.html').read_text()
    assert "connect-src 'none'" in html and '@media print' in html
    browser = next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium') if shutil.which(n)),None)
    if not browser:
        raise RuntimeError('real-browser-required')
    page_html = html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-files-') as td:
        page=Path(td)/'index.html';page.write_text(page_html)
        for layout,dimensions in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/layout),dimensions,'60000','30000'],capture_output=True,text=True,timeout=130)
            if result.returncode:
                raise RuntimeError('private-browser-did-not-complete')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))!=33:
                raise RuntimeError('file-desk-rejected: '+str(report.get('reason','check-count')))
            assert (layout=='narrow')==(report['width']<=760)
            validation=validate_outputs(report.pop('artifacts'))
            reports.append({'layout':layout,**report,'independent_validation':validation})
    print(json.dumps({'schema':'nexus.pilot-17.file-desk-witness.v1','status':'PASS','reports':reports,'authority':'none','real_user_tested':False}))

if __name__=='__main__':
    main()
