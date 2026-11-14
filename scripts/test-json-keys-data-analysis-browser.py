#!/usr/bin/env python3
"""Candidate duplicate JSON key rejection; keep the published compatibility witness stable."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis_browser', ROOT/'scripts/test-local-data-analysis-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
anchor = "    'group-mean-uses-nonmissing-numeric-cases');"
assert module.WITNESS.count(anchor) == 1
extra = r"""
  const validFields='[{"Score":1},{"Score":3}]',duplicateCases=[
   ['plain','[{"Score":1,"Score":99}]'],
   ['escaped','[{"Score":1,"\\u0053core":99}]'],
   ['proto','[{"__proto__":"first","__proto__":"second"}]'],
   ['shadowed','[{"Score":{"nested":1},"Score":99}]']
  ];
  await add([new File([validFields],'valid-fields.json')]);
  for(const [label,raw] of duplicateCases){
   pick('valid-fields.json');await run(true);assert(!$('analysis-download').disabled&&$('analysis-summary').textContent.includes('2 × 1'),'offline-'+label+'-starts-with-valid-analysis');
   await add([new File([raw],'duplicate-'+label+'.json')]);pick('duplicate-'+label+'.json');await run(false);
   assert(!$('analysis-summary').textContent&&$('analysis-download').disabled&&$('analysis-claim').disabled,'offline-'+label+'-duplicate-clears-stale-analysis');
   assert($('analysis-state').textContent.includes('duplicate JSON field names'),'offline-'+label+'-duplicate-error-is-actionable');
   const count=downloads.length;$('analysis-download').click();assert(downloads.length===count,'offline-'+label+'-duplicate-cannot-export-stale-result');
  }
  await add([new File(['[{"Score":1},{"\\u0053core":3}]'],'valid-escaped.json')]);pick('valid-escaped.json');await run(true);$('analysis-download').click();const escapedKeys=JSON.parse(await downloads.at(-1).blob.text());assert(escapedKeys.rows===2&&escapedKeys.columns===1&&escapedKeys.column_stats[0].summary.mean===2,'offline-same-decoded-key-across-rows-is-valid');
  await add([new File(['[{"text":"{\\\"a\\\":1,\\\"a\\\":2}","Score":3}]'],'inert-key-text.json')]);pick('inert-key-text.json');await run(true);$('analysis-download').click();const inertKeys=JSON.parse(await downloads.at(-1).blob.text());assert(inertKeys.column_stats[0].top_values[0].value==='{"a":1,"a":2}','offline-duplicate-looking-text-remains-inert');
  select('ui-language','fa');pick('duplicate-plain.json');$('analysis-run').click();await wait(()=>$('analysis-state').textContent.includes('تکراری'));assert($('analysis-download').disabled&&!$('analysis-summary').textContent,'offline-persian-duplicate-error-is-actionable');
  select('ui-language','en');pick('valid-fields.json');await run(true);assert(!$('analysis-download').disabled,'offline-valid-input-recovers-after-rejection');
"""
module.WITNESS = module.WITNESS.replace(anchor, anchor + '\n' + extra)
if __name__ == '__main__':
    module.main()
