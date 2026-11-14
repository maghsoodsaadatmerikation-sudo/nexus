#!/usr/bin/env python3
"""Candidate numeric boundaries; keep the published compatibility witness stable."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis_browser', ROOT/'scripts/test-local-data-analysis-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
anchor = "    'group-mean-uses-nonmissing-numeric-cases');"
assert module.WITNESS.count(anchor) == 1
extra = r"""
  await add([new File(['[{"id":9007199254740992},{"id":9007199254740993}]'],'numeric-identifiers.json')]);pick('numeric-identifiers.json');await run(true);select('analysis-group','0');select('analysis-metric','-1');$('analysis-download').click();
  const numericIds=JSON.parse(await downloads.at(-1).blob.text());assert(numericIds.groups.length===2&&numericIds.groups.some(g=>g.label==='9007199254740993'),'offline-json-identifiers-retain-exact-identity');
  await add([new File(['v\n-1e308\n0\n1e308\n'],'numeric-extremes.csv')]);pick('numeric-extremes.csv');await run(true);$('analysis-download').click();
  const extremeReport=JSON.parse(await downloads.at(-1).blob.text());assert($('analysis-bars').querySelectorAll('.analysis-track').length===8&&extremeReport.column_stats[0].summary.mean===0,'extreme-range-histogram-renders-without-overflow');
  await add([new File(['v\n5e-324\n5e-324\n'],'numeric-tiny.csv')]);pick('numeric-tiny.csv');await run(true);$('analysis-download').click();
  const tinyReport=JSON.parse(await downloads.at(-1).blob.text());assert(tinyReport.column_stats[0].summary.median===Number.MIN_VALUE,'offline-subnormal-median-remains-nonzero');
  await add([new File(['[{"v":1},{"v":2},{"v":3},{"v":4},{"v":1e-400}]'],'numeric-underflow.json')]);pick('numeric-underflow.json');await run(true);$('analysis-download').click();
  const underflowReport=JSON.parse(await downloads.at(-1).blob.text()).column_stats[0];assert(underflowReport.summary.mean===2.5&&underflowReport.invalid_numeric===1&&$('analysis-summary').textContent.includes('invalid=1'),'offline-underflow-is-excluded-and-disclosed');
"""
module.WITNESS = module.WITNESS.replace(anchor, anchor + '\n' + extra)
if __name__ == '__main__':
    module.main()
