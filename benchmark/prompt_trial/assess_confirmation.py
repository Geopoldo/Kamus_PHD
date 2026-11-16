"""Fixed clear reviewed passages for confirmation pages; CPU only."""
import json,re,runpy,hashlib
from pathlib import Path
from parse import parse
from evaluate import counts,chars
B=Path(__file__).resolve().parent.parent;R=B/'experiments/prompt_pilot_v1/confirmation-20261114-v1';O=R/'quality';O.mkdir(exist_ok=True)
H=runpy.run_path(str(B/'assistant_reference_v2/build.py'));H['verify']();ref=json.loads((B/'assistant_reference_v2/transcriptions.json').read_text());pages={p['page_number']:p for p in ref['documents'][2]['pages']}
def norm(t):
 t=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',t)
 t=re.sub(r'\b(?:[A-Za-z]\.[ \t]*)+[A-Za-z]\.?(?=\s|$|[,;:])',lambda m:re.sub('[^a-z]','',m[0].lower()),t)
 return H['normalize'](t).split()
records=[]
for model in ['qwen3.5-9b','qwen3.8-27b']:
 for variant in ['baseline_original','literal_regions_v1']:
  for number in [1,3,4,5,6,7,8]:
   sample=f'pdf_page_{number:02}';path=B/'extended_results'/model/(sample+'.txt') if variant=='baseline_original' else R/'raw'/variant/model/(sample+'.txt')
   raw=path.read_text();parsed=parse(raw,variant!='baseline_original');text='';orig=[]
   for seg in parsed['segments']:text+=seg['text'];orig.extend(range(seg['start'],seg['end_exclusive']))
   page=pages[number];regions={r['region_id'].split('.')[-1]:r for r in page['regions']};passages=[]
   def add(key,selections,start,end=None,include=False,drop=None,layer='active'):
    lines=[l for rid,lo,hi in selections for l in regions[rid]['lines'][lo-1:hi]]
    segs=[s for l in lines for s in l['segments'] if (s['state']=='deleted')==(layer=='deleted')]
    assert all(s['certainty']=='clear' for s in segs),(number,key)
    reference='\n'.join(''.join(s['text'] for s in l['segments'] if (s['state']=='deleted')==(layer=='deleted')) for l in lines)
    a=text.lower().index(start.lower());b=len(text) if end is None else text.lower().index(end.lower(),a+len(start))+(len(end) if include else 0)
    spans=[(a,b)]
    for phrase in drop or []:
     at=text.lower().find(phrase.lower(),a,b)
     if at>=0:
      d=at+len(phrase);spans=[z for i,j in spans for z in ([(i,min(j,at))] if i<at else [])+([(max(i,d),j)] if j>d else []) if z[0]<z[1]]
    hypo=''.join(text[i:j] for i,j in spans).strip();w=counts(norm(reference),norm(hypo));c=counts(chars(reference),chars(hypo))
    passages.append(dict(passage_id=key,layer=layer,reference_line_ids=[l['line_id'] for l in lines],reference=reference,hypothesis=hypo,word=w,character=c,clean_spans=spans,raw_spans=[dict(start=orig[i],end_exclusive=orig[j-1]+1) for i,j in spans],review_status='verified',reviewer='assistant reviewed saved output against fixed Astra reference'))
   if number==1:
    add('chronology', [('r04',1,1),('r05',1,4),('r06',1,5)],'Till 1893','Till 1949')
    add('JAG_duties',[('r07',1,7)],'Till 1949','jurisdiction',True,drop=['Prosecution'])
    add('review',[('r13',1,1)],'Review of all','Prosecution' if 'Prosecution' in text[text.index('Review of all'):] else None)
   if number==3:
    add('constitution',[('r03',1,2)],'Any 3','(2)')
    add('scope',[('r04',1,9)],'(2)','determines')
    add('certificate',[('r05',1,4)],'(3)','(b)')
    add('grounds_command',[('r05',8,15)],'grounds','(c)')
   if number==4:
    add('header',[('r01',1,1)],'British','3 of')
    add('deleted_line',[('r02',1,1)],'3 of',layer='deleted')
   if number==5:
    add('review_1',[('r03',1,3)],'1. Convening','2.')
    add('review_2',[('r04',1,2)],'2.','3.')
    add('review_3',[('r05',1,3)],'3.','Trained')
    add('review_4',[('r06',1,3)],'4. Special','5.')
    add('review_5',[('r07',1,3)],'5. New','English - From')
   if number==6:
    add('header',[('r01',1,1)],'Removal','U.M.C.J.')
    add('appoints_counsel',[('r03',1,3)],'U.M.C.J. Convening','English Convening',drop=['Court\nand\nCounsel.','Court and Counsel.'])
    add('legal_aid',[('r05',1,6)],'English Convening','legal aid basis',True)
    # All outputs visibly share this phrase, despite other deleted labels.
    add('approval',[('r07',4,6)],'- Convening Authority','U.M.C.J. No doubt',drop=['Judge.','Court\nand\nCounsel.','Court and Counsel.'])
    add('review_law',[('r09',6,8)],'But the review','real supervisory')
   if number==7:
    # Numeral spelling normalized; start after list label to avoid mixing recognition and label style.
    add('first',[('r02',1,8)],'The English','Would assignment')
    row=passages[-1];row['hypothesis']=re.sub(r'\s*(?:②|\(2\))\s*$','',row['hypothesis']);row['reference']=re.sub(r'^①\s*','',row['reference']);row['word']=counts(norm(row['reference']),norm(row['hypothesis']));row['character']=counts(chars(row['reference']),chars(row['hypothesis']))
    add('assignment',[('r03',1,1),('r04',1,1),('r03',2,4)],'Would assignment','officers')
    row=passages[-1];row['reference']=re.sub(r'^②\s*','',row['reference']);row['word']=counts(norm(row['reference']),norm(row['hypothesis']));row['character']=counts(chars(row['reference']),chars(row['hypothesis']))
    add('control',[('r06',4,7)],'control, unless','C.O. How')
   if number==8:
    add('chief',[('r02',2,3)],'get away','The J')
    add('effective',[('r03',1,1)],'To make Corps effective','to accomplish')
    add('court',[('r04',1,4)],'impossible','same as to defense')
    row=passages[-1];row['hypothesis']=re.sub(r'\s*(?:②|\(2\))\s*$','',row['hypothesis']);row['reference']=re.sub(r'^①\s*','',row['reference']);row['word']=counts(norm(row['reference']),norm(row['hypothesis']));row['character']=counts(chars(row['reference']),chars(row['hypothesis']))
    end=next(x for x in ['rated','ruled','tried'] if x in text.lower())
    add('military_officer',[('r05',4,5)],'proposed. Any military',end)
    add('law_officer',[('r06',1,2)],'same as to law','man')
    row=passages[-1];row['reference']=re.sub(r'^③\s*','',row['reference']);row['word']=counts(norm(row['reference']),norm(row['hypothesis']));row['character']=counts(chars(row['reference']),chars(row['hypothesis']))
   # Preserve every unscored substring; no claim of total insertion coverage.
   covered=bytearray(len(text))
   for p in passages:
    for a,b in p['clean_spans']:
     assert not any(covered[a:b]),(model,number,p['passage_id']);covered[a:b]=b'\1'*(b-a)
   excluded=[];i=0
   while i<len(text):
    if covered[i]:i+=1;continue
    j=i+1
    while j<len(text) and not covered[j]:j+=1
    excluded.append(dict(start=i,end=j,text=text[i:j],reason='Outside fixed reviewed passages; uncertainty, region assignment, numbering, or auxiliary text'));i=j
   records.append(dict(model=model,variant=variant,sample=sample,page_id=page['page_id'],path=str(path),sha256=hashlib.sha256(raw.encode()).hexdigest(),passages=passages,excluded=excluded,parser_errors=parsed['errors']))
(O/'paired_results.json').write_text(json.dumps(dict(records=records,method='Fixed clear contiguous passages reviewed by assistant; no reference corrections; recognition ignores emitted state labels; physical CER, v2 normalized words plus spaced dotted initials.'),indent=2,ensure_ascii=False)+'\n');print('Records:',len(records))
H['verify']()
