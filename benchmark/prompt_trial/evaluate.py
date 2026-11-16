"""Metrics for explicitly reviewed, exhaustive, nonoverlapping assignments."""
import hashlib,re,unicodedata

def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def words(t):
 t=unicodedata.normalize('NFKC',t).casefold()
 t=re.sub(r'\b[^\W\d_](?:\.[^\W\d_])+(?:\.)?(?!\w)',lambda m:m[0].replace('.',''),t)
 t=re.sub(r"(?<=\w)['’](?=\w)",'',t)
 return re.findall(r'[^\W_]+',t)
def chars(t):return ' '.join(unicodedata.normalize('NFKC',t).split())
def counts(a,b):
 p=[(j,0,0,0,j) for j in range(len(b)+1)]
 for i,x in enumerate(a,1):
  c=[(i,0,0,i,0)]
  for j,y in enumerate(b,1):
   e,h,s,d,k=p[j-1];v=(e+(x!=y),h-(x==y),s+(x!=y),d,k)
   e,h,s,d,k=p[j];w=(e+1,h,s,d+1,k)
   e,h,s,d,k=c[-1];z=(e+1,h,s,d,k+1)
   c.append(min(v,w,z))
  p=c
 e,h,s,d,k=p[-1];return dict(H=-h,S=s,D=d,I=k,N=len(a),M=len(b),errors=e)
def validate_assignments(text,rows):
 covered=bytearray(len(text))
 for row in rows:
  if row['hypothesis_sha256']!=sha(text):raise ValueError('Hypothesis changed')
  if row['review_status'] not in ['verified','omitted','extra']:raise ValueError('Assignment pending review')
  for span in row['hypothesis_spans']:
   a,b=span['start'],span['end_exclusive']
   if not 0<=a<=b<=len(text):raise ValueError('Offset out of range')
   if any(covered[a:b]):raise ValueError('Overlapping spans')
   covered[a:b]=b'\1'*(b-a)
 if not all(covered):raise ValueError('Unassigned output characters')
def score(reference,hypothesis):
 w=counts(words(reference),words(hypothesis));c=counts(chars(reference),chars(hypothesis))
 return dict(word=w,character=c,wer=w['errors']/w['N'] if w['N'] else None,cer=c['errors']/c['N'] if c['N'] else None)
