"""Reviewed paired passages. Does not edit Astra or use GPU.
Explicit textual anchors document human-reviewed span boundaries, not best-match retrieval.
"""
import json,re,hashlib,runpy,sys
from pathlib import Path
from evaluate import counts,chars
from parse import parse
B=Path(__file__).resolve().parent.parent;RUN=B/'experiments/prompt_pilot_v1/pilot-20261114-v1';OUT=RUN/'quality';OUT.mkdir(exist_ok=True)
REF=B/'assistant_reference_v2/transcriptions.json';helper=runpy.run_path(str(B/'assistant_reference_v2/build.py'));helper['verify']();ref=json.loads(REF.read_text());pages={p['page_id']:p for d in ref['documents'] for p in d['pages']}
def norm(t):
 t=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',t)
 t=re.sub(r'\b(?:[A-Za-z]\.[ \t]*)+[A-Za-z]\.?(?=\s|$|[,;:])',lambda m:re.sub('[^a-z]','',m[0].lower()),t)
 return helper['normalize'](t).split()
def take(text,start,end=None,include=False):
 a=text.index(start);b=len(text) if end is None else text.index(end,a+len(start))+(len(end) if include else 0)
 return a,b
records=[]
for model in ['qwen3.5-9b','qwen3.8-27b']:
 for variant in ['baseline_original','literal_regions_v1']:
  for sample,pid in [('typed','typed_letter_1914.p01'),('handwritten','handwritten_letter_1865.p01'),('pdf_page_02','british_system_notes.p02')]:
   path=B/('extended_results' if sample.startswith('pdf') else 'results')/model/(sample+'.txt') if variant=='baseline_original' else RUN/'raw'/variant/model/(sample+'.txt')
   raw=path.read_text();parsed=parse(raw,variant!='baseline_original')
   # Retain an exact per-character map back to raw text while removing only known tags.
   clean='';origin=[]
   for seg in parsed['segments']:
    clean+=seg['text'];origin.extend(range(seg['start'],seg['end_exclusive']))
   page=pages[pid];regions={r['region_id'].split('.')[-1]:r for r in page['regions']};selected=[]
   def add(key,rid,lo,hi,start,end=None,include=False,exclude=None):
    lines=regions[rid]['lines'][lo-1:hi];assert all(s['certainty']=='clear' for l in lines for s in helper['active_segments'](l))
    a,b=take(clean,start,end,include);spans=[(a,b)]
    # Explicit, reviewed disjoint margin removal for baseline mixed into body; preserve it in excluded ledger.
    for x,y in exclude or []:
     c,d=take(clean,x,y,False);spans=[(i,min(j,c)) for i,j in spans if i<c]+[(max(i,d),j) for i,j in spans if j>d]
    spans=[(i,j) for i,j in spans if i<j]
    hypothesis=''.join(clean[i:j] for i,j in spans).strip()
    reference=helper['joined_literal'](lines)
    # Literal CER uses physical source text (NFKC + whitespace), WER joins only explicit line continuations.
    literal='\n'.join(helper['literal_active'](l) for l in lines)
    w=counts(norm(reference),norm(hypothesis));c=counts(chars(literal),chars(hypothesis))
    selected.append(dict(passage_id=key,reference_line_ids=[l['line_id'] for l in lines],reference=reference,literal_reference=literal,hypothesis=hypothesis,clean_spans=spans,raw_spans=[dict(start=origin[i],end_exclusive=origin[j-1]+1) for i,j in spans],word=w,character=c,review_status='verified',reviewer='assistant; direct reading of saved outputs against frozen Astra; no reference changes'))
   if sample=='typed':
    add('main_header','r01',1,5,'"THE CHURCH','BOARD OF DIRECTORS' if model=='qwen3.5-9b' else 'OFFICIAL ORGAN')
    add('organ','r02',1,3,'OFFICIAL ORGAN','NEW YORK CITY DISTRICT')
    add('district_clear','r03',1,3,'NEW YORK CITY DISTRICT','156 FIFTH AVE.')
    add('board','r04',1,13,'BOARD OF DIRECTORS','OFFICIAL ORGAN' if model=='qwen3.5-9b' else 'NEW YORK July')
    # In 27B the date follows the board; whitespace before July may vary, fixed input reviewed.
    add('date','r05',1,1,'NEW YORK\nJuly' if model=='qwen3.5-9b' and variant=='baseline_original' else 'NEW YORK July','Col. Theodore')
    add('body','r06',1,38,'Col. Theodore','We Have Moved')
    add('footer','r07',1,2,'We Have Moved')
   elif sample=='handwritten':
    # Only completely clear contiguous reference passages; no uncertain words used as scoring anchors.
    add('date','r03',1,1,'New Orleans','My Dear')
    add('salutation','r04',1,1,'My Dear','I am')
    add('opening','r05',1,2,'I am','a seeming')
    add('resources_revenue','r05',10,15,'ago ','now to present it.',True)
    add('comparatively','r06',1,1,('Confederating' if model=='qwen3.5-9b' else 'Considering' if variant=='baseline_original' else 'Contemplating'),'the lands')
    add('levees','r06',3,7,'Cairo','culture')
    # Folios evaluated separately to avoid content/order confound.
   else:
    add('appointment','r05',1,3,'(1) J.A.G.','(2) Army')
    exclusion=[]
    if 'This composed Army' in clean:
     exclusion=[('This composed Army','Army (Air Force) Legal Services.')]
    # Split mixed body/margin explicitly rather than silently counting margin as body.
    a,b=take(clean,'(2) Army','(3) J.A.G');chunk=clean[a:b]
    # Preserve exact span segments for removed intrusive margin lines.
    removals=[]
    for phrase in ['This composed ','of Officers ','7 Officers\n']:
     at=chunk.find(phrase)
     if at>=0:removals.append((a+at,a+at+len(phrase)))
    # add then replace that record with reviewed separated spans below.
    add('army_services','r06',1,4,'(2) Army','(3) J.A.G')
    row=selected[-1];spans=[(a,b)]
    for c,d in sorted(removals,reverse=True):
     spans=[part for i,j in spans for part in ([(i,min(j,c))] if i<c else [])+([(max(i,d),j)] if j>d else []) if part[0]<part[1]]
    row['clean_spans']=spans;row['raw_spans']=[dict(start=origin[i],end_exclusive=origin[j-1]+1) for i,j in spans];row['hypothesis']=''.join(clean[i:j] for i,j in spans).strip();row['word']=counts(norm(row['reference']),norm(row['hypothesis']));row['character']=counts(chars(row['literal_reference']),chars(row['hypothesis']))
    add('judicial_functions','r08',1,5,'(3) J.A.G','(c) Tendering advice',True)
    # Deleted uncertain case word explicitly excluded from recognition of Review Records.
    row=selected[-1]
    h=row['hypothesis'];h=re.sub(r'\bCase,?\s*','',h);row['derived_exclusion']='Case belongs to uncertain deleted reference segment; original span and hypothesis retained';row['scored_hypothesis']=h;row['word']=counts(norm(row['reference']),norm(h));row['character']=counts(chars(row['literal_reference']),chars(h))
    add('deputy_assistants','r11',2,4,'J.A. =','Courts-Martial')
    add('court_makeup','r16',1,3,'(1) Make up','Panel')
   # Check selected clean spans don't overlap; every other character explicitly excluded from this scoped comparison.
   covered=bytearray(len(clean))
   for x in selected:
    for a,b in x['clean_spans']:
     assert not any(covered[a:b]),(model,sample,x['passage_id']);covered[a:b]=b'\1'*(b-a)
   excluded=[];i=0
   while i<len(clean):
    if covered[i]:i+=1;continue
    j=i+1
    while j<len(clean) and not covered[j]:j+=1
    excluded.append(dict(clean_start=i,clean_end=j,text=clean[i:j],reason='Outside fixed reviewed clear passages: uncertainty, margins/deletions, folios or formatting; not silently scored as hallucination'));i=j
   records.append(dict(model=model,variant=variant,sample=sample,page_id=pid,path=str(path),sha256=hashlib.sha256(raw.encode()).hexdigest(),passages=selected,excluded=excluded,parser_errors=parsed['errors']))

def aggregate(rs):
 out={}
 for key in ['word','character']:
  c={k:sum(p[key][k] for r in rs for p in r['passages']) for k in ['H','S','D','I','N','M','errors']};c['rate_percent']=100*c['errors']/c['N'] if c['N'] else None;out[key]=c
 return out
summary=[dict(model=m,variant=v,**aggregate([r for r in records if r['model']==m and r['variant']==v])) for m in ['qwen3.5-9b','qwen3.8-27b'] for v in ['baseline_original','literal_regions_v1']]
assert len({x['word']['N'] for x in summary})==1
result=dict(reference_sha256=hashlib.sha256(REF.read_bytes()).hexdigest(),scope='Reviewed fixed clear passages, not all strict units. Recognition irrespective of emitted DEL labels; structure assessed separately.',normalization='v2 words plus dotted initials with spaces normalized consistently (D. D. = D.D.); explicit physical hyphen-line joining for WER. CER physical text NFKC whitespace collapsed, case/punctuation preserved, no lexical repairs.',summary=summary,records=records)
(OUT/'paired_results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(summary,indent=2))
helper['verify']()
