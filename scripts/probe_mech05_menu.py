#!/usr/bin/env python3
import os,sys,time,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OSW=Path('/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1'); SWC=Path('/home/mjh/Projects/CoDesk-candidate-repair-20261104'); IMAGE=OSW/'docker_vm_data/osworld-v2-ubuntu-x86.qcow2'; OUT=Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls'); ASSETS=Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets')
sys.path[:0]=[str(ROOT),str(SWC),str(OSW)]; os.environ.update({'OSWORLD_DIR':str(OSW),'PARAGUI_TASK_ASSETS':str(ASSETS),'OSCOMBO_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_GUEST_IMAGE':str(IMAGE),'SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE':'swcub/osworld-v2.1-qemu-runtime:local','OSWORLD_DOCKER_RUNTIME_IMAGE':'swcub/osworld-v2.1-qemu-runtime:local','SWCUB_OSWORLD_OVERLAY_HOST_DIR':str(OUT/'overlays'),'SWCUB_OSWORLD_CACHE_DIR':str(OUT/'osworld-cache')})
from oscombo import combo
from oscombo.guest import Guest
from oscombo.osworld import load_task
from swcub.resource_safety import ensure_resource_identity
from tasks.mechanism_expansion_v1.mech05 import *
runid='mech05-menu-probe-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+str(os.getpid()); out=OUT/runid; out.mkdir(); (out/'overlays').mkdir(); os.environ.update({'SWCUB_RUN_ID':runid,'SWCUB_OWNER_TOKEN':secrets.token_hex(32),'SWCUB_RESOURCE_LEDGER':str(out/'resource-events.jsonl')}); os.environ.pop('SWCUB_RESOURCE_IDENTITY_INITIALIZED',None); ensure_resource_identity(out/'resource-events.jsonl')
env=None
try:
 tasks=[load_task(str(ROOT/'tasks/mechanism_expansion_v1/task_mech05a.py')),load_task(str(ROOT/'tasks/mechanism_expansion_v1/task_mech05b.py'))]
 env=combo.boot(str(IMAGE),str(out/'cache')); combo.setup_tasks(env,tasks); time.sleep(4); g=Guest(env)
 g.execute(['bash','-lc','xrandr --current > /tmp/mech05-xrandr.txt; xdotool key --clearmodifiers alt+e; sleep .5'],20); (out/'edit-menu.png').write_bytes(g.screenshot(patience=90)); g.execute(['bash','-lc','xdotool mousemove --sync 190 430 click 1; sleep .7'],20); (out/'track-changes-submenu.png').write_bytes(g.screenshot(patience=90)); print(g.execute(['bash','-lc','cat /tmp/mech05-xrandr.txt | head -20'],10))
 print(out)
finally:
 if env: env.close()
