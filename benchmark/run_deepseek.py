import os,sys,time,json,traceback,threading,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['HF_MODULES_CACHE']=str(ROOT/'hf-modules')
os.environ['HF_HUB_OFFLINE']='1'
# Load the Blackwell-compatible torch stack before reusing older Transformers.
import torch, torchvision
sys.path.insert(0,'/home/ewok/LIIA/DeepseekOCR2/ocr-backend/.venv/lib/python3.12/site-packages')
from transformers import AutoTokenizer,AutoModel
MODEL='/home/ewok/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-OCR-2/snapshots/fdee390b3b35687ac6016795fb81c74c1af109ac'
if __name__=='__main__':
    from run_qwen import memory_available_gib,gpu_free_mib
    if memory_available_gib()<12 or gpu_free_mib()<14000:raise RuntimeError('Memory preflight stopped DeepSeek loading')
    print('torch',torch.__version__,'CUDA',torch.cuda.is_available(),flush=True)
    t=time.perf_counter()
    tokenizer=AutoTokenizer.from_pretrained(MODEL,trust_remote_code=True,local_files_only=True)
    model=AutoModel.from_pretrained(MODEL,trust_remote_code=True,local_files_only=True,torch_dtype=torch.bfloat16,_attn_implementation='eager').eval().cuda()
    load=time.perf_counter()-t
    def memory_guard():
        while True:
            time.sleep(3)
            if memory_available_gib()<4 or gpu_free_mib()<1024:
                print('MEMORY_GUARD_STOP',flush=True)
                os.kill(os.getpid(),signal.SIGTERM)
    threading.Thread(target=memory_guard,daemon=True).start()
    mode=sys.argv[1] if len(sys.argv)>1 else 'free'
    prompt='<image>\n<|grounding|>Convert the document to markdown.' if mode=='markdown' else '<image>\nFree OCR.'
    extended='--extended' in sys.argv
    if extended:
        original_generate=model.generate
        def capped_generate(*args,**kwargs):
            kwargs['max_new_tokens']=4096
            return original_generate(*args,**kwargs)
        model.generate=capped_generate
    out=ROOT/('extended_results' if extended else 'results')/('deepseek-ocr-2-markdown' if mode=='markdown' else 'deepseek-ocr-2'); out.mkdir(parents=True,exist_ok=True)
    samples=[('typed','f67aa551-e1b3-477f-ab3c-322c97ca816b.png'),('handwritten','75f90bd0-f4a2-459a-bd26-591e3e6122fd.png')]
    if extended: samples=[(f'pdf_page_{i:02}',str((ROOT/'extended_inputs'/f'pdf_page_{i:02}.png').resolve())) for i in range(1,9)]
    for label,name in samples:
        if (out/(label+'.json')).exists():continue
        torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize(); t=time.perf_counter()
        text=model.infer(tokenizer,prompt=prompt,image_file=str(Path('/home/ewok/claude_code_env/uploads')/name),output_path=str(out/label),base_size=1024,image_size=768,crop_mode=True,save_results=False,eval_mode=True)
        torch.cuda.synchronize(); elapsed=time.perf_counter()-t
        (out/(label+'.txt')).write_text(text)
        result=dict(sample=label,seconds=elapsed,load_seconds=load,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,prompt=prompt,base_size=1024,image_size=768,crop_mode=True,model=MODEL)
        (out/(label+'.json')).write_text(json.dumps(result,indent=2)); print(json.dumps(result),flush=True)
