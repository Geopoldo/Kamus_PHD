import base64,json,os,subprocess,time,urllib.request,urllib.error,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SERVER='/home/ewok/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.28.2/llama-server'
PROMPT='Transcribe all visible text in this historical document image, in reading order. Preserve the original English spelling, names, dates, and paragraph structure. Do not summarize, translate, modernize, or complete text outside the image. Mark genuinely unreadable words as [illegible]. Return only the transcription.'
MODELS=[('qwen3-vl-8b','Qwen3-VL-8B-Instruct-GGUF','Qwen3VL-8B-Instruct-Q4_K_M.gguf','mmproj-Qwen3VL-8B-Instruct-F16.gguf'),('qwen3.5-9b','Qwen3.5-9B-GGUF','Qwen3.5-9B-Q4_K_M.gguf','mmproj-Qwen3.5-9B-BF16.gguf')]
SAMPLES=[('typed','f67aa551-e1b3-477f-ab3c-322c97ca816b.png'),('handwritten','75f90bd0-f4a2-459a-bd26-591e3e6122fd.png')]
def request(path,payload=None,timeout=20):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('http://127.0.0.1:18765'+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
def gpu():
    try: return subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip()
    except Exception:return None
def memory_available_gib():
    values={line.split(':',1)[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line and line.split()[1].isdigit()}
    return values['MemAvailable']/1024**2
def gpu_free_mib():
    return int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0])
if __name__=='__main__':
    extended='--extended' in sys.argv
    if extended: SAMPLES=[(f'pdf_page_{i:02}',str((ROOT/'extended_inputs'/f'pdf_page_{i:02}.png').resolve())) for i in range(1,9)]
    large='--large' in sys.argv
    if large:
        MODELS=[('qwen3.6-27b','Qwen3.6-27B-GGUF','Qwen3.6-27B-Q4_K_M.gguf','mmproj-Qwen3.6-27B-BF16.gguf'),
                ('qwen3.8-27b','Qwen3.8-27B-GGUF','Qwen3.8-27B-Q4_K_M.gguf','mmproj-Qwen3.8-27B-BF16.gguf')]
    if '--only' in sys.argv:
        selected=sys.argv[sys.argv.index('--only')+1]
        MODELS=[m for m in MODELS if m[0]==selected]
        if not MODELS:raise ValueError('Unknown model selection: '+selected)
    gpu_layers='48' if large else 'all'
    for label,folder,weights,projector in MODELS:
        out=ROOT/('extended_results' if extended else 'results')/label;out.mkdir(parents=True,exist_ok=True)
        model=ROOT/'models'/folder/weights; proj=ROOT/'models'/folder/projector
        print('WAITING_FOR_FILES',label,flush=True)
        while not (model.exists() and proj.exists()): time.sleep(5)
        if all((out/(s+'.json')).exists() for s,_ in SAMPLES):continue
        if memory_available_gib()<12 or gpu_free_mib()<14000:
            raise RuntimeError('Preflight stopped: need at least 12 GiB available RAM and 14000 MiB free VRAM before loading.')
        cmd=[SERVER,'-m',str(model),'--mmproj',str(proj),'--host','127.0.0.1','--port','18765','-ngl',gpu_layers,'-c','8192','-np','1','--image-max-tokens','4096','--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-webui']
        (out/'server-command.json').write_text(json.dumps(cmd,indent=2))
        log=(out/'server.log').open('w');started=time.perf_counter()
        process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        stop_monitor=threading.Event()
        resource_samples=[]
        def monitor():
            while not stop_monitor.wait(3):
                if process.poll() is not None:return
                try:
                    ram=memory_available_gib();vram=gpu_free_mib()
                    resource_samples.append({'ram_available_gib':ram,'vram_free_mib':vram})
                    if ram<4 or vram<1024:
                        print('MEMORY_GUARD_STOP',ram,vram,flush=True)
                        process.terminate();return
                except (OSError,ValueError,subprocess.SubprocessError):return
        try:
            while True:
                if process.poll() is not None:raise RuntimeError('Server exited; see '+str(out/'server.log'))
                if time.perf_counter()-started>300:raise TimeoutError('Model loading timeout')
                try:
                    if request('/health',timeout=2).get('status')=='ok':break
                except (OSError,urllib.error.HTTPError):time.sleep(1)
            load=time.perf_counter()-started;print('LOADED',label,load,'seconds',gpu(),'MiB',flush=True)
            if gpu_free_mib()<2000 or memory_available_gib()<8:
                raise RuntimeError('Stopped after loading: require at least 2000 MiB VRAM and 8 GiB RAM available.')
            watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
            for sample,filename in SAMPLES:
                if (out/(sample+'.json')).exists():continue
                if gpu_free_mib()<1500 or memory_available_gib()<6:
                    raise RuntimeError('Stopped before inference: insufficient memory reserve.')
                image=Path('/home/ewok/claude_code_env/uploads')/filename
                encoded=base64.b64encode(image.read_bytes()).decode()
                payload={'model':label,'messages':[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+encoded}}]}],'temperature':0,'seed':42,'max_tokens':4096,'stream':False,'cache_prompt':False}
                started=time.perf_counter(); response=request('/v1/chat/completions',payload,timeout=1800);elapsed=time.perf_counter()-started
                (out/(sample+'-response.json')).write_text(json.dumps(response,indent=2))
                (out/(sample+'.txt')).write_text(response['choices'][0]['message']['content'] or '')
                result={'model':label,'sample':sample,'seconds':elapsed,'load_seconds':load,'gpu_used_mib_after':gpu(),'usage':response.get('usage'),'timings':response.get('timings'),'finish_reason':response['choices'][0].get('finish_reason'),'prompt':PROMPT,'temperature':0,'seed':42,'max_tokens':4096,'image_max_tokens':4096,'context':8192,'quantization':'Q4_K_M','gpu_layers_requested':gpu_layers,'offload_note':'Partial GPU + CPU/RAM' if large else 'All layers on GPU'}
                (out/(sample+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
        finally:
            stop_monitor.set()
            process.terminate()
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            (out/'memory-monitor.json').write_text(json.dumps(resource_samples,indent=2))
            log.close()
