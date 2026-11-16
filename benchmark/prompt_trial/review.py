"""Create lossless review packets; score only reviewed explicit reference units.
python review.py prepare --text FILE --output ASSIGNMENTS.json
python review.py score --text FILE --assignments ASSIGNMENTS.json --output RESULTS.json
"""
import argparse,json,runpy
from pathlib import Path
from evaluate import validate_assignments,score,sha
from parse import parse
B=Path(__file__).resolve().parent.parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','score']);ap.add_argument('--text',type=Path,required=True);ap.add_argument('--assignments',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 raw=args.text.read_text();ref=json.loads((B/'assistant_reference_v2/evaluation_units.json').read_text());lookup={x['unit_id']:x for x in ref['units']}
 if args.action=='prepare':
  parsed=parse(raw,False);rows=[]
  # Partition text at every parser boundary, keeping even formatting and whitespace.
  boundaries=sorted({0,len(raw)}|{x[k] for x in parsed['segments']+parsed['format_spans'] for k in ['start','end_exclusive']})
  for a,b in zip(boundaries,boundaries[1:]):
   rows.append(dict(hypothesis_sha256=sha(raw),hypothesis_spans=[dict(start=a,end_exclusive=b)],preview=raw[a:b],reference_unit_ids=[],reference_layer='active',review_status='needs_review',disposition='unassigned',reason='Review and merge spans into comparable passages; preserve exhaustive disjoint coverage.'))
  result=dict(text_path=str(args.text.resolve()),rows=rows,reference_candidates=[x for x in ref['units']],instructions='Every clear reference unit in the selected page must appear exactly once, including omitted units with no spans. Excluded reference uncertainties must have explicit reviewed boundaries. Format/whitespace spans may be classified format; additions must be extra, never format.')
 else:
  runpy.run_path(str(B/'assistant_reference_v2/build.py'))['verify']()
  packet=json.loads(args.assignments.read_text());rows=packet['rows'];validate_assignments(raw,rows);seen=set();results=[]
  pages=packet.get('page_ids',[])
  if not pages:raise ValueError('Set page_ids before scoring')
  for row in rows:
   ids=row['reference_unit_ids']
   for uid in ids:
    if uid in seen:raise ValueError('Reference unit reused')
    seen.add(uid)
    if lookup[uid]['page_id'] not in pages:raise ValueError('Wrong reference page')
   disposition=row.get('disposition')
   if disposition not in ['content','extra','format','reference_uncertain']:raise ValueError('Unresolved disposition')
   if not row.get('reason'):raise ValueError('Review reason required')
   if disposition=='format':
    if ids:raise ValueError('Format cannot consume reference')
    continue
   if disposition=='reference_uncertain':
    if not ids or any(lookup[x]['strict_eligible'] for x in ids):raise ValueError('Exclusion must be supported by uncertain reference units')
    continue
   if any(not lookup[x]['strict_eligible'] for x in ids):raise ValueError('Uncertain reference cannot be scored')
   if disposition=='content' and not ids:raise ValueError('Content needs reference units')
   reference='\n'.join(lookup[x]['literal_active_text'] for x in ids)
   hypothesis=''.join(raw[s['start']:s['end_exclusive']] for s in row['hypothesis_spans'])
   # Strip only recognized format markers. Explicit abstentions remain nonmatching tokens.
   parsed=parse(hypothesis,False)
   hypothesis=''.join(' \ufffd ' if s['abstention'] else s['text'] for s in parsed['segments'])
   # CER uses raw physical text with collapsed whitespace; WER uses explicitly provided joins.
   # Require manual join spans instead of guessing lexical repairs.
   reference_words='\n'.join(lookup[x]['reconstructed_word_text'] for x in ids)
   for old,new in row.get('verified_word_joins',[]):
    if old not in hypothesis:raise ValueError('Join source absent')
    if old.replace('-\n','').replace('\n','')!=new:raise ValueError('Join must only remove physical line break/hyphen')
    hypothesis=hypothesis.replace(old,new,1)
   metrics=score(reference,hypothesis);metrics['word']=score(reference_words,hypothesis)['word'];w=metrics['word'];metrics['wer']=w['errors']/w['N'] if w['N'] else None
   results.append(dict(reference_unit_ids=ids,reference=reference,hypothesis=hypothesis,metrics=metrics))
  expected={u['unit_id'] for u in lookup.values() if u['page_id'] in pages and u['strict_eligible']}
  if not expected<=seen:raise ValueError('Clear reference units missing from review: '+str(sorted(expected-seen)))
  totals={key:{k:sum(x['metrics'][key][k] for x in results) for k in ['H','S','D','I','N','M','errors']} for key in ['word','character']}
  result=dict(rows=results,totals=totals,wer=totals['word']['errors']/totals['word']['N'] if totals['word']['N'] else None,cer=totals['character']['errors']/totals['character']['N'] if totals['character']['N'] else None,profile='CER physical-text NFKC whitespace collapsed, case/punctuation preserved; WER v2 normalized words with reviewed joins',assignment_sha256=sha(args.assignments.read_text()))
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
