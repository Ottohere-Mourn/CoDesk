#!/usr/bin/env python3
"""No-Guest Qwen generate probe using a captured OSWorld agent request."""
import argparse, base64, hashlib, json, os, queue, subprocess, threading, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path("/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk")
MODEL=Path("/home1/mjh/Projects/CoDesk-V0-A6000/models/Qwen/Qwen3-VL-30B-A3B-Instruct")
DEFAULT_MESSAGES=Path('/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/model-smoke/a6000-qwen-writer-calc-solo-20260930-r04-stage-timing/model-actors/writer_actor/draft/message_cache/messages_step_0.json')

def nvidia_sample():
    try:
        p=subprocess.run(['nvidia-smi','--query-gpu=index,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        return {'returncode':p.returncode,'rows':p.stdout.strip().splitlines(),'error':p.stderr.strip()}
    except Exception as e:return {'error':f'{type(e).__name__}: {e}'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--messages',type=Path,default=DEFAULT_MESSAGES)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--max-new-tokens',type=int,default=128)
    ap.add_argument('--attention',choices=('eager','sdpa'),default='eager');args=ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True); started=time.monotonic()
    result={'started_utc':datetime.now(timezone.utc).isoformat(),'host':os.uname().nodename,
        'visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'checkpoint':str(MODEL),
        'dtype':'bfloat16','quantization':None,'max_memory':{'cuda:0':'40GiB','cpu':'80GiB'},
        'attention_backend':args.attention,'max_new_tokens':args.max_new_tokens,'do_sample':False,
        'messages_file':str(args.messages),'status':'starting','telemetry':[]}
    done=threading.Event()
    def sample_loop():
        import psutil
        proc=psutil.Process(os.getpid())
        while not done.is_set():
            result['telemetry'].append({'elapsed_s':round(time.monotonic()-started,2),
                'cpu_percent':proc.cpu_percent(interval=None),'rss_bytes':proc.memory_info().rss,
                'nvidia_smi':nvidia_sample()})
            done.wait(1)
    sampler=threading.Thread(target=sample_loop,daemon=True);sampler.start()
    try:
        import torch
        from transformers import AutoConfig,AutoProcessor,Qwen3VLMoeForConditionalGeneration,TextIteratorStreamer
        from qwen_vl_utils import process_vision_info
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
        config=AutoConfig.from_pretrained(str(MODEL),local_files_only=True)
        processor=AutoProcessor.from_pretrained(str(MODEL),local_files_only=True)
        # Input is an archived, real screenshot request from Qwen3VLAgent. Keep its prompt/schema fixed.
        messages=json.loads(args.messages.read_text())
        image_hashes=[];image_dims=[]
        for msg in messages:
            content=msg.get('content')
            if not isinstance(content,list):continue
            for part in content:
                if part.get('type')!='image_url':continue
                url=part['image_url']['url']; raw=base64.b64decode(url.split(',',1)[1])
                image_hashes.append(hashlib.sha256(raw).hexdigest())
                from PIL import Image
                import io
                with Image.open(io.BytesIO(raw)) as im:image_dims.append(list(im.size))
        result.update({'model_type':config.model_type,'architectures':config.architectures,
            'config_sha256':hashlib.sha256((MODEL/'config.json').read_bytes()).hexdigest(),
            'screenshot_count':len(image_hashes),'screenshot_sha256':image_hashes,'screenshot_dimensions':image_dims})
        model_started=time.monotonic()
        model=Qwen3VLMoeForConditionalGeneration.from_pretrained(str(MODEL),torch_dtype=torch.bfloat16,
            device_map='auto',max_memory={0:'40GiB','cpu':'80GiB'},local_files_only=True,
            low_cpu_mem_usage=True,attn_implementation=args.attention)
        model.eval()
        device_map={str(k):str(v) for k,v in getattr(model,'hf_device_map',{}).items()}
        from collections import Counter
        result.update({'model_load_s':round(time.monotonic()-model_started,2),
            'hf_device_map':device_map,'module_count_by_device':dict(Counter(device_map.values())),
            'gpu_memory_allocated_after_load':[torch.cuda.memory_allocated(i) for i in range(torch.cuda.device_count())],
            'gpu_memory_reserved_after_load':[torch.cuda.memory_reserved(i) for i in range(torch.cuda.device_count())]})
        converted=[]
        # The message cache matches local_qwen_worker input protocol.
        for msg in messages:
            content=msg.get('content','')
            if isinstance(content,str):converted.append({'role':msg.get('role','user'),'content':content});continue
            parts=[]
            for part in content:
                if part.get('type')=='text':parts.append({'type':'text','text':str(part.get('text',''))})
                elif part.get('type')=='image_url':
                    from PIL import Image
                    import io
                    raw=base64.b64decode(part['image_url']['url'].split(',',1)[1])
                    with Image.open(io.BytesIO(raw)) as im:parts.append({'type':'image','image':im.convert('RGB')})
            converted.append({'role':msg.get('role','user'),'content':parts})
        rendered=processor.apply_chat_template(converted,tokenize=False,add_generation_prompt=True)
        image_inputs,video_inputs=process_vision_info(converted)
        inputs=processor(text=[rendered],images=image_inputs,videos=video_inputs,padding=True,return_tensors='pt').to(model.device)
        result['input_tokens']=int(inputs.input_ids.shape[1])
        streamer=TextIteratorStreamer(processor.tokenizer,skip_prompt=True,skip_special_tokens=True,timeout=2)
        errors=[]
        def generate():
            try:
                with torch.inference_mode():model.generate(**inputs,max_new_tokens=args.max_new_tokens,do_sample=False,streamer=streamer)
            except BaseException as e:
                errors.append(f'{type(e).__name__}: {e}')
                try:streamer.end()
                except Exception:pass
        thread=threading.Thread(target=generate,daemon=True);thread.start()
        gen_started=time.monotonic();first_token_s=None;chunks=[]
        deadline=gen_started+300
        while time.monotonic()<deadline:
            try:piece=next(streamer)
            except queue.Empty:
                if not thread.is_alive():break
                continue
            except StopIteration:break
            if piece:
                chunks.append(piece)
                if first_token_s is None:first_token_s=round(time.monotonic()-gen_started,3)
            if not thread.is_alive() and streamer.text_queue.empty():break
        thread.join(timeout=1)
        torch.cuda.synchronize()
        result.update({'generation_status':'completed' if not errors and not thread.is_alive() else 'generation_error',
            'first_nonempty_text_s':first_token_s,'generate_wall_s':round(time.monotonic()-gen_started,3),
            'generated_text':''.join(chunks),'generation_errors':errors,
            'gpu_max_memory_allocated':[torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())],
            'gpu_max_memory_reserved':[torch.cuda.max_memory_reserved(i) for i in range(torch.cuda.device_count())]})
        if thread.is_alive():result['generation_status']='timed_out_thread_still_alive'
        result['status']='pass' if first_token_s is not None and chunks else 'fail'
    except Exception as e:
        result.update({'status':'error','error':f'{type(e).__name__}: {e}','traceback':traceback.format_exc()})
    finally:
        done.set();sampler.join(timeout=3)
        result['wall_s']=round(time.monotonic()-started,2)
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({k:result.get(k) for k in ('status','generation_status','first_nonempty_text_s','generate_wall_s','module_count_by_device','gpu_max_memory_allocated','error','wall_s')},ensure_ascii=False),flush=True)
    return 0 if result.get('status')=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
