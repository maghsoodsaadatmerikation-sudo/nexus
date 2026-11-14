#!/usr/bin/env python3
"""Real candidate XLSX ZIP/XML coordinate checks; public compatibility stays stable."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analysis_browser',ROOT/'scripts/test-local-data-analysis-browser.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def cell(ref,value,kind='inlineStr'):
    content=f'<is><t>{value}</t></is>' if kind=='inlineStr' else f'<v>{value}</v>'
    return f'<c r="{ref}" t="{kind}">{content}</c>'
def row(number,cells):
    attr='' if number is None else f' r="{number}"'
    return f'<row{attr}>'+''.join(cells)+'</row>'
def header(ref='A1'):
    return row(1,[cell(ref,'Group'),cell('B1','Value')])
def package(rows):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as z:
        entries={
            '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
            '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            'xl/workbook.xml':f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Synthetic" sheetId="1" r:id="rId1"/></sheets></workbook>',
            'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{NS}"><sheetData>'+''.join(rows)+'</sheetData></worksheet>'
        }
        for name,text in entries.items():
            z.writestr(zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)),text)
    return base64.b64encode(buffer.getvalue()).decode()
fixtures={'valid':package([header(),row(2,[cell('A2','A'),cell('B2','1','n')]),row(3,[cell('A3','A'),cell('B3','3','n')])]),
          'sparse':package([header(),row(3,[cell('A3','A'),cell('B3','3','n')])]),
          'inferred':package([header(),row(None,[cell('A2','A'),cell('B2','3','n')])]),
          'empty':package([header(),row(2,[]),row(3,[cell('A3','A'),cell('B3','3','n')])]),
          'header':package([header('A2'),row(2,[cell('A2','A'),cell('B2','3','n')])]),
          'inferred-mismatch':package([header(),row(None,[cell('A3','A'),cell('B3','3','n')])]),
          'formula':package([header(),row(2,[cell('A2','A'),'<c r="B2"><f>1+2</f><v>3</v></c>'])])}
for label,refs in {'group':('A999','B2'),'metric':('A2','B999'),'zero':('A0','B2'),'unsafe':('A9007199254740993','B2')}.items():
    fixtures[label]=package([header(),row(2,[cell(refs[0],'A'),cell(refs[1],'3','n')])])
anchor="    'group-mean-uses-nonmissing-numeric-cases');"
assert module.WITNESS.count(anchor)==1
extra='\n const xlsxCoordinates='+json.dumps(fixtures,separators=(',',':'))+';\n'+r"""
 const xlsxBytes=raw=>Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
 await add([new File([xlsxBytes(xlsxCoordinates.valid)],'coordinates-valid.xlsx')]);
 for(const label of ['group','metric','zero','unsafe','header','inferred-mismatch']){
  pick('coordinates-valid.xlsx');await run(true);assert($('analysis-summary').textContent.includes('2 × 2')&&!$('analysis-download').disabled,'xlsx-'+label+'-starts-with-valid-analysis');
  await add([new File([xlsxBytes(xlsxCoordinates[label])],'coordinates-'+label+'.xlsx')]);pick('coordinates-'+label+'.xlsx');await run(false);
  assert(!$('analysis-summary').textContent&&$('analysis-download').disabled&&$('analysis-claim').disabled,'xlsx-'+label+'-inconsistent-reference-clears-stale-result');
  assert($('analysis-state').textContent.includes('cell coordinates do not match their row'),'xlsx-'+label+'-coordinate-error-is-actionable');
  const count=downloads.length;$('analysis-download').click();assert(downloads.length===count,'xlsx-'+label+'-cannot-export-stale-analysis');
 }
 pick('coordinates-valid.xlsx');await run(true);$('analysis-download').click();const validCoordinates=JSON.parse(await downloads.at(-1).blob.text());assert(validCoordinates.column_stats[1].summary.mean===2&&validCoordinates.rows===2,'xlsx-valid-coordinate-values-remain-supported');
 const rawCoordinateBytes=xlsxBytes(xlsxCoordinates.valid),coordinateSha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',rawCoordinateBytes)),c=>c.toString(16).padStart(2,'0')).join('');assert(validCoordinates.source.sha256===coordinateSha,'xlsx-accepted-source-retains-raw-byte-identity');
 for(const label of ['sparse','inferred','empty']){
  await add([new File([xlsxBytes(xlsxCoordinates[label])],'coordinates-'+label+'.xlsx')]);pick('coordinates-'+label+'.xlsx');await run(true);$('analysis-download').click();const coordinateReport=JSON.parse(await downloads.at(-1).blob.text());
  assert(coordinateReport.rows===(label==='inferred'?1:2)&&coordinateReport.column_stats[1].missing===(label==='inferred'?0:1)&&coordinateReport.column_stats[1].summary.mean===3,'xlsx-'+label+'-row-semantics-preserved');
 }
 await add([new File([xlsxBytes(xlsxCoordinates.formula)],'coordinates-formula.xlsx')]);pick('coordinates-formula.xlsx');await run(false);assert($('analysis-download').disabled&&!$('analysis-summary').textContent,'xlsx-formula-rejection-remains-enforced');
 select('ui-language','fa');pick('coordinates-group.xlsx');$('analysis-run').click();await wait(()=>$('analysis-state').textContent.includes('سازگار نیست'));assert($('analysis-download').disabled&&!$('analysis-summary').textContent,'xlsx-persian-coordinate-error-is-actionable');
 select('ui-language','en');pick('coordinates-valid.xlsx');await run(true);assert(!$('analysis-download').disabled,'xlsx-valid-input-recovers-after-coordinate-rejection');
"""
module.WITNESS=module.WITNESS.replace(anchor,anchor+'\n'+extra)
if __name__=='__main__':module.main()
