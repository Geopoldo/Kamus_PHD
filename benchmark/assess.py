"""Small-sample evaluation. WER covers only the manually read typewritten body."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def normalize(text):
    text=re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>',' ',text,flags=re.S)
    text=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',text)
    return re.findall(r"[a-z0-9]+",text.lower())
def distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]
ref=normalize((ROOT/'reference_typed_body.txt').read_text())
results=[]
for folder in sorted((ROOT/'results').iterdir()):
    if not (folder/'typed.txt').exists():continue
    text=(folder/'typed.txt').read_text()
    tokens=normalize(text)
    # Exclude letterhead, recipient block and footer, which the reference omits.
    starts=[i for i in range(len(tokens)-2) if tokens[i:i+3]==['my','dear','col']]
    ends=[i for i,t in enumerate(tokens) if t=='candidacy']
    if not starts or not ends:metric={'error':'Body boundaries not found; manual review needed'}
    else:
        body=tokens[starts[0]:ends[-1]+1]; edits=distance(ref,body)
        metric={'reference_words':len(ref),'output_words':len(body),'word_edits':edits,'wer':edits/len(ref),'scope':'Manually read typewritten body only; lowercased, punctuation ignored; letterhead not scored'}
    handwritten=(folder/'handwritten.txt').read_text() if (folder/'handwritten.txt').exists() else ''
    anchors=['new orleans','garfield','mississippi','levees']
    normalized=' '.join(normalize(handwritten))
    row={'model':folder.name,'typed_body':metric,'handwritten_anchor_presence':{x:x in normalized for x in anchors},'handwritten_scoring_note':'Anchor presence is diagnostic only, not a transcription accuracy percentage. No complete verified handwritten reference exists.'}
    snippets=['New Orleans','1865','Garfield','Comparatively','Mississippi Basin','efficient levees']
    row['handwritten_review_snippets']={x:(' '.join(normalize(x)) in normalized) for x in snippets}
    for sample in ['typed','handwritten']:
        p=folder/(sample+'.json')
        if p.exists():row[sample+'_run']=json.loads(p.read_text())
    monitor=folder/'memory-monitor.json'
    if monitor.exists():
        observations=json.loads(monitor.read_text())
        if observations:
            row['resource_monitor']={'sample_count':len(observations),'minimum_available_ram_gib':min(x['ram_available_gib'] for x in observations),'minimum_free_vram_mib':min(x['vram_free_mib'] for x in observations),'monitor_interval_seconds':3,'note':'Observed during inference, excludes model loading. GPU values are free VRAM; RAM uses Linux MemAvailable.'}
    results.append(row)
source=Path('/home/ewok/claude_code_env/uploads')
manifest=[{'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(source.glob('*.png'))]
summary={'reference_review':{'method':'Body checked against enlarged upper and lower image regions.','corrected_words':341,'correction_note':'The initial manual reference contained four word edits: an inserted as, that instead of it, an inserted such, and a missing and. Earlier WER values of 1.2% for DeepSeek/Qwen3.5 and 3.5% for Qwen3-VL are superseded.'},'limitations':['Two unique pages only; not representative of the full collection.','One timed request per page/configuration, excluding loading. Times are indicative; no repeated warm runs.','DeepSeek BF16/eager and Qwen Q4_K_M/llama.cpp use different runtimes and prompts; this compares practical configurations, not controlled model architectures.','27B Qwen models use partial GPU offload (48 layers) and CPU/RAM. Smaller Qwen models are entirely on GPU.','Handwritten quality requires manual review.','The sample pages do not validate recall of the Excel priority terms.'],'images':manifest,'results':results}
(ROOT/'comparison.json').write_text(json.dumps(summary,indent=2))
for row in results:print(json.dumps({'model':row['model'],'typed_body':row['typed_body'],'handwritten_anchors':row['handwritten_anchor_presence'],'typed_seconds':row.get('typed_run',{}).get('seconds'),'handwritten_seconds':row.get('handwritten_run',{}).get('seconds')},ensure_ascii=False))
