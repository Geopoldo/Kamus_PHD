import concurrent.futures, json, time, sys, os
from pathlib import Path
os.environ['HF_XET_HIGH_PERFORMANCE']='0'
os.environ['HF_XET_NUM_CONCURRENT_RANGE_GETS']='4'
from huggingface_hub import hf_hub_download, model_info

ROOT=Path(__file__).resolve().parent
JOBS=[('Qwen/Qwen3-VL-8B-Instruct-GGUF','Qwen3VL-8B-Instruct-Q4_K_M.gguf'),
      ('Qwen/Qwen3-VL-8B-Instruct-GGUF','mmproj-Qwen3VL-8B-Instruct-F16.gguf'),
      ('lmstudio-community/Qwen3.5-9B-GGUF','Qwen3.5-9B-Q4_K_M.gguf'),
      ('lmstudio-community/Qwen3.5-9B-GGUF','mmproj-Qwen3.5-9B-BF16.gguf')]
def get(job):
    repo,name=job
    info=model_info(repo)
    print('DOWNLOAD',repo,name,info.sha,flush=True)
    path=hf_hub_download(repo,name,revision=info.sha,local_dir=ROOT/'models'/repo.split('/')[-1],cache_dir=ROOT/'hf-cache')
    result=dict(repo=repo,file=name,revision=info.sha,path=path,bytes=Path(path).stat().st_size)
    print('DONE',json.dumps(result),flush=True)
    return result
if __name__=='__main__':
    large='--large' in sys.argv
    if large:
        JOBS=[('lmstudio-community/Qwen3.6-27B-GGUF','Qwen3.6-27B-Q4_K_M.gguf'),
              ('lmstudio-community/Qwen3.6-27B-GGUF','mmproj-Qwen3.6-27B-BF16.gguf'),
              ('lmstudio-community/Qwen3.8-27B-GGUF','Qwen3.8-27B-Q4_K_M.gguf'),
              ('lmstudio-community/Qwen3.8-27B-GGUF','mmproj-Qwen3.8-27B-BF16.gguf')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if large else 2) as pool:
        results=list(pool.map(get,JOBS))
    (ROOT/('models-27b.json' if large else 'models.json')).write_text(json.dumps(results,indent=2))
