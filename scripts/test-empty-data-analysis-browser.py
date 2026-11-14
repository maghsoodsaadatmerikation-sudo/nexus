#!/usr/bin/env python3
"""Candidate empty-record boundaries; keep the published compatibility witness stable."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis_browser', ROOT/'scripts/test-local-data-analysis-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
anchor = "    'group-mean-uses-nonmissing-numeric-cases');"
assert module.WITNESS.count(anchor) == 1
extra = r"""
  for(const [kind,sep] of [['csv',','],['tsv','\t']]){
   const raw=`Group${sep}Value\r\nA${sep}1\r\n${sep}\r\n""${sep}""\r\nB${sep}3\r\n`;
   await add([new File([raw],'empty-records.'+kind)]);pick('empty-records.'+kind);await run(true);select('analysis-group','0');select('analysis-metric','1');$('analysis-download').click();const emptyReport=JSON.parse(await downloads.at(-1).blob.text());
   assert(emptyReport.rows===4&&emptyReport.column_stats.every(c=>c.missing===2),'offline-'+kind+'-empty-records-and-missing-counts');
   assert(emptyReport.column_stats[1].summary.count===2&&emptyReport.column_stats[1].summary.mean===2,'offline-'+kind+'-missing-records-are-not-zero');
   const missing=emptyReport.groups.find(g=>g.missing);assert(missing.count===2&&missing.numeric_n===0&&missing.metric_mean===null&&emptyReport.groups.reduce((n,g)=>n+g.count,0)===4,'offline-'+kind+'-all-records-in-exported-groups');
   assert($('analysis-summary').textContent.includes('4 × 2')&&$('analysis-summary').textContent.includes('Missing 2'),'offline-'+kind+'-all-records-visible');
   await add([new File(['Value\n""\n'],'only-missing.'+kind)]);pick('only-missing.'+kind);await run(true);$('analysis-download').click();const allMissing=JSON.parse(await downloads.at(-1).blob.text());assert(allMissing.rows===1&&allMissing.column_stats[0].missing===1&&allMissing.column_stats[0].summary===null,'offline-'+kind+'-single-empty-record-is-accepted');
   await add([new File(['Value\n1\n\n3\n'],'blank-record.'+kind)]);pick('blank-record.'+kind);await run(true);$('analysis-download').click();const blank=JSON.parse(await downloads.at(-1).blob.text());assert(blank.rows===3&&blank.column_stats[0].missing===1,'offline-'+kind+'-blank-record-counted-without-trailing-ghost');
  }
"""
module.WITNESS = module.WITNESS.replace(anchor, anchor + '\n' + extra)
if __name__ == '__main__':
    module.main()
