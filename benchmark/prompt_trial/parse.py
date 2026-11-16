"""Lossless offsets over raw Unicode text; no reference-dependent repairs."""
import re
TAG=re.compile(r'\[REGION (R\d+) (header|body|margin|footer|folio|other)\]|\[END_REGION\]|\[/?(?:DEL|INS|UNCLEAR)\]|\[ILLEGIBLE\]',re.I)
def parse(text,structured=True):
 segments=[];errors=[];region=None;state='active';uncertain=False;last=0;ids=set();tags=[]
 def emit(a,b):
  if a<b:segments.append(dict(start=a,end_exclusive=b,text=text[a:b],region=region,state=state,uncertain=uncertain,abstention=False))
 for m in TAG.finditer(text):
  emit(last,m.start());tag=m[0].upper();tags.append(dict(start=m.start(),end_exclusive=m.end()))
  if m.group(1):
   if region:errors.append('nested_region')
   if m.group(1) in ids:errors.append('duplicate_region')
   ids.add(m.group(1));region={'id':m.group(1),'kind':m.group(2).lower()}
  elif tag=='[END_REGION]':
   if not region or state!='active' or uncertain:errors.append('invalid_region_close')
   region=None;state='active';uncertain=False
  elif tag in ['[DEL]','[INS]']:
   if state!='active':errors.append('nested_state')
   state='deleted' if tag=='[DEL]' else 'inserted'
  elif tag in ['[/DEL]','[/INS]']:
   if state!=('deleted' if tag=='[/DEL]' else 'inserted'):errors.append('invalid_state_close')
   state='active'
  elif tag=='[UNCLEAR]':
   if uncertain:errors.append('nested_uncertainty')
   uncertain=True
  elif tag=='[/UNCLEAR]':
   if not uncertain:errors.append('invalid_uncertainty_close')
   uncertain=False
  else:segments.append(dict(start=m.start(),end_exclusive=m.end(),text=m[0],region=region,state=state,uncertain=True,abstention=True))
  last=m.end()
 emit(last,len(text))
 if region or state!='active' or uncertain:errors.append('unclosed_tag')
 if structured and not ids:errors.append('missing_regions')
 if structured and any(s['region'] is None and s['text'].strip() for s in segments):errors.append('text_outside_regions')
 return dict(segments=segments,format_spans=tags,errors=errors)
