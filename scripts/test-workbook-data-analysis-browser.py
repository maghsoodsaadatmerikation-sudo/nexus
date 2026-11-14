#!/usr/bin/env python3
"""Candidate workbook order, relationship identity and disclosed sheet provenance."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
module=load('analysis_browser','test-local-data-analysis-browser.py')
f=load('xlsx_fixtures','test-xlsx-data-analysis-browser.py')
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
def mutate(base,updates,remove=()):
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(base))) as z:entries={n:z.read(n).decode() for n in z.namelist()}
    entries.update(updates)
    for name in remove:entries.pop(name,None)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as z:
        for name,text in entries.items():z.writestr(zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)),text)
    return base64.b64encode(buffer.getvalue()).decode()
def workbook(name='Actual',state='visible'):
    return f'<workbook xmlns="{f.NS}" xmlns:link="{REL}"><sheets><sheet name="{name}" sheetId="9" link:id="rId9" state="{state}"/><sheet name="Decoy" sheetId="1" link:id="rId1"/></sheets></workbook>'
def relations(target='worksheets/sheet9.xml',mode='',extra=''):
    return f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId9" Type="{REL}/worksheet" Target="{target}"{mode}/>{extra}</Relationships>'
selected=f'<worksheet xmlns="{f.NS}"><sheetData>'+f.header()+f.row(2,[f.cell('A2','Actual'),f.cell('B2','9','n')])+'</sheetData></worksheet>'
base=f.package([f.header(),f.row(2,[f.cell('A2','Decoy'),f.cell('B2','99','n')])])
ordered=mutate(base,{'xl/workbook.xml':workbook(),'xl/_rels/workbook.xml.rels':relations(),'xl/worksheets/sheet9.xml':selected})
fixtures={'ordered':ordered,
 'absolute':mutate(ordered,{'xl/_rels/workbook.xml.rels':relations('/xl/worksheets/custom.xml'),'xl/worksheets/custom.xml':selected}),
 'hidden':mutate(ordered,{'xl/workbook.xml':workbook('Hidden &lt;img src=x&gt;','hidden')}),
 'external':mutate(ordered,{'xl/_rels/workbook.xml.rels':relations('https://example.invalid/sheet.xml',' TargetMode="External"')}),
 'missing':mutate(ordered,{},['xl/workbook.xml']),
 'unknown':mutate(ordered,{'xl/_rels/workbook.xml.rels':relations().replace('Id="rId9"','Id="other"')}),
 'duplicate':mutate(ordered,{'xl/_rels/workbook.xml.rels':relations(extra=f'<Relationship Id="rId9" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>')})}
shared_sheet=f'<worksheet xmlns="{f.NS}"><sheetData>'+f.header()+f.row(2,[f.cell('A2','0','s'),f.cell('B2','1','s')])+'</sheetData></worksheet>'
fixtures['shared']=mutate(ordered,{'xl/worksheets/sheet9.xml':shared_sheet,'xl/_rels/workbook.xml.rels':relations(extra=f'<Relationship Id="s" Type="{REL}/sharedStrings" Target="strings/custom.xml"/>'),'xl/strings/custom.xml':f'<sst xmlns="{f.NS}"><si><t>Actual</t></si><si><t>7</t></si></sst>','xl/sharedStrings.xml':f'<sst xmlns="{f.NS}"><si><t>Wrong</t></si><si><t>999</t></si></sst>'})
with zipfile.ZipFile(io.BytesIO(base64.b64decode(ordered))) as z:strict={n:z.read(n).decode().replace(f.NS,'http://purl.oclc.org/ooxml/spreadsheetml/main').replace(REL,'http://purl.oclc.org/ooxml/officeDocument/relationships') for n in z.namelist()}
fixtures['strict']=mutate(ordered,strict)
anchor="    'group-mean-uses-nonmissing-numeric-cases');";assert module.WITNESS.count(anchor)==1
extra='\nconst workbooks='+json.dumps(fixtures,separators=(',',':'))+';\n'+r"""
 const workbookBytes=raw=>Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
 await add([new File([workbookBytes(workbooks.ordered)],'workbook-ordered.xlsx')]);pick('workbook-ordered.xlsx');await run(true);$('analysis-download').click();const orderedWorkbook=JSON.parse(await downloads.at(-1).blob.text()),chosen=orderedWorkbook.source.worksheet;
 assert(orderedWorkbook.column_stats[1].summary.mean===9&&chosen.name==='Actual'&&chosen.part==='xl/worksheets/sheet9.xml'&&chosen.sheet_count===2&&chosen.selection==='first-listed-sheet','workbook-order-and-relationship-select-correct-values');
 assert($('analysis-summary').textContent.includes('Analyzed worksheet: Actual (1/2)')&&$('analysis-summary').textContent.includes('other sheets are excluded'),'workbook-selection-and-coverage-visible');
 const workbookSha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',workbookBytes(workbooks.ordered))),n=>n.toString(16).padStart(2,'0')).join('');assert(orderedWorkbook.source.sha256===workbookSha,'workbook-source-hash-remains-raw-byte-identity');
 for(const label of ['external','missing','unknown','duplicate']){
  pick('workbook-ordered.xlsx');await run(true);assert(!$('analysis-download').disabled,'workbook-'+label+'-starts-with-valid-analysis');
  await add([new File([workbookBytes(workbooks[label])],'workbook-'+label+'.xlsx')]);pick('workbook-'+label+'.xlsx');await run(false);
  assert(!$('analysis-summary').textContent&&$('analysis-download').disabled&&$('analysis-claim').disabled,'workbook-'+label+'-ambiguous-selection-clears-stale-result');
  assert($('analysis-state').textContent.includes('sheet relationships'),'workbook-'+label+'-selection-error-is-actionable');
  const count=downloads.length;$('analysis-download').click();assert(downloads.length===count,'workbook-'+label+'-cannot-export-stale-result');
 }
 for(const label of ['absolute','shared','strict','hidden']){
  await add([new File([workbookBytes(workbooks[label])],'workbook-'+label+'.xlsx')]);pick('workbook-'+label+'.xlsx');await run(true);$('analysis-download').click();const selectedWorkbook=JSON.parse(await downloads.at(-1).blob.text());
  assert(selectedWorkbook.column_stats[1].summary.mean===(label==='shared'?7:9),'workbook-'+label+'-relationship-values-preserved');
  if(label==='absolute')assert(selectedWorkbook.source.worksheet.part==='xl/worksheets/custom.xml','workbook-absolute-target-provenance-preserved');
  if(label==='hidden')assert(selectedWorkbook.source.worksheet.state==='hidden'&&$('analysis-summary').textContent.includes('Hidden <img src=x>')&&$('analysis-summary').textContent.includes('selected sheet is hidden')&&!$('analysis-summary').querySelector('img'),'workbook-hidden-state-disclosed-and-name-inert');
 }
 select('ui-language','fa');pick('workbook-external.xlsx');$('analysis-run').click();await wait(()=>$('analysis-state').textContent.includes('رابطه‌های برگه'));assert($('analysis-download').disabled,'workbook-persian-selection-error-is-actionable');
 pick('workbook-ordered.xlsx');$('analysis-run').click();await wait(()=>$('analysis-summary').textContent.includes('برگهٔ تحلیل‌شده'));assert($('analysis-summary').textContent.includes('Actual (1/2)'),'workbook-selection-label-translates');
 select('ui-language','en');assert(!$('analysis-download').disabled,'workbook-valid-input-recovers-after-rejection');
"""
module.WITNESS=module.WITNESS.replace(anchor,anchor+'\n'+extra)
if __name__=='__main__':module.main()
