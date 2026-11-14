#!/usr/bin/env python3
"""Candidate-only completeness assertions, separate from the pinned public contract."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis_browser', ROOT/'scripts/test-local-data-analysis-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
anchor = "    'group-mean-uses-nonmissing-numeric-cases');"
assert module.WITNESS.count(anchor) == 1
extra = r"""
  const many='Group,Value\n'+Array.from({length:14},(_,i)=>'G'+String(i).padStart(2,'0')+','+i).join('\n');
  await add([new File([many],'many-groups.csv',{type:'text/csv'})]);pick('many-groups.csv');await run(true);
  select('analysis-group','0');select('analysis-metric','1');
  assert($('analysis-summary').textContent.includes('12/14')&&$('analysis-bars').querySelectorAll('.analysis-track').length===10&&$('analysis-bars').textContent.includes('10/14'),'offline-group-preview-discloses-coverage');
  $('analysis-download').click();const allGroups=JSON.parse(await downloads.at(-1).blob.text());
  assert(allGroups.groups.length===14&&allGroups.group_count===14&&allGroups.groups_complete===true,'offline-json-export-retains-all-groups');
  assert(allGroups.metric==='Value'&&allGroups.group_by==='Group'&&allGroups.groups.reduce((n,g)=>n+g.count,0)===14,'offline-group-export-identifies-metric-and-all-row-counts');
"""
module.WITNESS = module.WITNESS.replace(anchor, anchor + '\n' + extra)

if __name__ == '__main__':
    module.main()
