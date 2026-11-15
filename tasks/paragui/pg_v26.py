import requests
from evaluation_examples.task_class import pg_common as pc
from evaluation_examples.task_class import pg_v456_oracle as oracle
NAME="v26";PORT=8161;MARKER=pc.HOME+'/.codesk-'+NAME+'-setup'
def _ready(sc):
 try:
  r=requests.post(f'http://{sc.vm_ip}:{sc.server_port}/execute',json={'command':['bash','-lc',f'test -f {MARKER} && echo READY'],'shell':False,'timeout':20},timeout=25)
  return 'READY' in (r.json().get('output') or '')
 except Exception:return False
def setup(sc):
 if _ready(sc):return
 pc.start_webapp(sc,f'{NAME}/app_{NAME}.py',NAME,PORT,f'{NAME}/seed.db')
 pc.open_chrome(sc,[f'http://127.0.0.1:{PORT}/desk'])
 pc.sh(sc,f'touch {MARKER}')
def state(env):
 return pc.sql(env,pc.webapp_db(NAME),{'items':'SELECT id,kind,name,details,clip_ref,facts,data_a,data_b,version FROM items ORDER BY rowid','desk':'SELECT active_id,active_panel,rev FROM desk WHERE id=1','events':'SELECT id,item_id,panel,payload FROM events ORDER BY id'})
def evaluate(env,panel,dest):
 c,s=oracle.checks(state(env),pc.expected(NAME),panel,NAME)
 return pc.result(s,c)
