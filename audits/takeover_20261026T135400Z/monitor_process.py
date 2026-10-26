"""Read-only fallback for rootless Docker's unavailable CPU cgroup counters."""
import json,sys,time
from pathlib import Path
import docker,psutil
root=Path(sys.argv[1]).resolve()
client=docker.DockerClient(base_url='unix:///data3/whn/Project2/.codesk-docker/docker.sock',timeout=5)
seen=False
try:
 while True:
  containers=client.containers.list(filters={'label':['oscombo=1','oscombo.run='+root.name]})
  if containers:seen=True
  if not containers and seen and ((root/'result.json').exists() or (root/'failure.json').exists()):break
  for c in containers:
   try:
    pid=c.attrs['State']['Pid']; p=psutil.Process(pid)
    if 'qemu' not in p.name():raise RuntimeError('expected QEMU process')
    row={'time':time.time(),'container_id':c.id,'pid':pid,'process_created':p.create_time(),
         'cpu_seconds':p.cpu_times().user+p.cpu_times().system,'rss_bytes':p.memory_info().rss,
         'threads':p.num_threads(),'scope':'host QEMU process; excludes Docker daemon overhead'}
   except Exception as exc:row={'time':time.time(),'container_id':c.id,'error_type':type(exc).__name__}
   with (root/'qemu_process_resources.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  time.sleep(5)
finally:client.close()
