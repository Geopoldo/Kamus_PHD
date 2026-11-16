"""Score complete crop responses, retaining missing outputs as deletions."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'prompt_trial'))
from evaluate import score
ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--reference',type=Path,default=ROOT/'reference.json');args=ap.parse_args()
rows=[]
for region in json.loads(args.reference.read_text())['regions']:
 path=args.run/'raw/baseline_original/qwen3.5-9b'/f"{region['id']}.txt"
 text=path.read_text() if path.exists() else ''
 rows.append(dict(id=region['id'],page=region['page'],missing=not path.exists(),**score(region['reference'],text)))
totals={k:sum(r['word'][k] for r in rows) for k in ['H','S','D','I','N','M','errors']}
result=dict(scope='Clear active regions only; full crop output scored, including extras. Not comparable directly with historical selected-passage WER.',regions=rows,word=totals,wer=totals['errors']/totals['N'])
(args.run/'region_scores.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(word=totals,wer=result['wer'],missing=sum(r['missing'] for r in rows))))
