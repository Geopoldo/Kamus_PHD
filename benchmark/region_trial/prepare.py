"""Freeze clear active regions before inference; never pass reference text to runner."""
import hashlib,json,math
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
B=ROOT.parent
source=B/'assistant_reference_v2/transcriptions.json'
data=json.loads(source.read_text())
rows=[];samples={}
for doc in data['documents']:
 for page in doc['pages']:
  image=Image.open(page.get('oriented_image_path',page['image_path']))
  for region in page['regions']:
   segments=[s for line in region['lines'] for s in line['segments']]
   if not segments or any(s['certainty']!='clear' or s['state']!='active' for s in segments):continue
   key=region['region_id']; box=region['bbox']; w,h=image.size
   pixels=[max(0,math.floor(box[0]*w)),max(0,math.floor(box[1]*h)),min(w,math.ceil(box[2]*w)),min(h,math.ceil(box[3]*h))]
   path=ROOT/'inputs'/f'{key}.png';path.parent.mkdir(exist_ok=True)
   image.crop(pixels).save(path)
   samples[key]=str(path)
   rows.append(dict(id=key,page=page['page_id'],box=pixels,reference='\n'.join(''.join(s['text'] for s in line['segments']) for line in region['lines']),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
config=json.loads((B/'prompt_trial/pilot.json').read_text());config.update(models=['qwen3.5-9b'],variant='baseline_original',samples=samples)
(ROOT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
(ROOT/'reference.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Entire regions whose segments are all clear and active; other regions excluded before inference.',regions=rows),indent=2)+'\n')
print(len(rows),'regions prepared')
