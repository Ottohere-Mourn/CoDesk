"""Read-only real MCP/Guest transport probe; no model or GUI mutation."""
import asyncio,base64,io,json,os,time
from pathlib import Path
import docker
from PIL import Image
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path('/data3/whn/Project2/CoDesk')
RUN=ROOT/'runs/cdd-scripted-isolated-20261026T151600Z'
OUT=RUN/'mcp_readonly_probe'
OUT.mkdir(exist_ok=False)
async def main():
 c=docker.DockerClient(base_url='unix:///data3/whn/Project2/.codesk-docker/docker.sock')
 meta=json.loads((RUN/'provenance.json').read_text());cid=next(g['container_id'] for g in meta['guests'] if g['key']=='A');v=c.containers.get(cid)
 assert len(cid)==64 and v.labels['oscombo.run']==RUN.name and v.labels['oscombo']=='1'
 port=v.attrs['NetworkSettings']['Ports']['5000/tcp'][0]['HostPort'];c.close()
 env={'PATH':os.environ['PATH'],'PYTHONPATH':str(ROOT),'OSCOMBO_GUEST_URL':'http://127.0.0.1:'+port,'OSCOMBO_ACTION_LOG':str(OUT/'actions.jsonl'),'OSCOMBO_MAX_STEPS':'2','OSCOMBO_MCP_TURN_COOLDOWN_SEC':'0'}
 params=StdioServerParameters(command='/data3/whn/Project2/OSWorld-V2/.venv/bin/python',args=['-m','oscombo.desktop_tools','--mcp'],env=env)
 t=time.time()
 async with stdio_client(params,errlog=(OUT/'stderr.log').open('w')) as (read,write):
  async with ClientSession(read,write) as s:
   await s.initialize();listing=await s.list_tools();response=await s.call_tool('screenshot',{})
   assert not response.isError
   images=[b for b in response.content if b.type=='image'];assert len(images)==1
   png=base64.b64decode(images[0].data);(OUT/'model_view.png').write_bytes(png)
   with Image.open(io.BytesIO(png)) as im:assert im.size==(1280,720)
   result={'status':'PASS_REAL_GUEST_MCP_SCREENSHOT','model_called':False,'gui_mutation':False,'container_id':cid,'run_id':RUN.name,'guest':'A','tools':[t.name for t in listing.tools],'image_size':[1280,720],'started_at':t,'ended_at':time.time(),'scope':'real STDIO MCP startup, tool enumeration and actual Guest screenshot only; not model vision/inference validation'}
   (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
asyncio.run(main())
