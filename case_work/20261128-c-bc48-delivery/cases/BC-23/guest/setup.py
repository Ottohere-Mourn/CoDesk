from __future__ import annotations
import argparse,csv,json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw
from zipfile import ZIP_STORED,ZipFile
def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--source-dir',required=True);p.add_argument('--start-service',action='store_true');p.add_argument('--open-browser',action='store_true');a=p.parse_args();r=Path(a.workspace).expanduser().resolve()/'release_lab';(r/'assets').mkdir(parents=True,exist_ok=True);(r/'out/client').mkdir(parents=True,exist_ok=True);(r/'out/server').mkdir(parents=True,exist_ok=True);(r/'qa').mkdir(exist_ok=True)
 Image.new('RGB',(800,450),(31,74,110)).save(r/'assets/client_source.png');Image.new('RGB',(128,128),(235,153,57)).save(r/'assets/brand_mark.png')
 with ZipFile(r/'assets/client_source.ora','w') as z:
  z.writestr('mimetype','image/openraster',compress_type=ZIP_STORED);z.writestr('stack.xml','<image version="0.0.1" w="800" h="450" name="Client Launch Artwork"><stack><layer name="Brand mark" src="data/brand_mark.png" x="40" y="40" opacity="1.0" visibility="visible" composite-op="svg:src-over"/><layer name="Background" src="data/background.png" x="0" y="0" opacity="1.0" visibility="visible" composite-op="svg:src-over"/></stack></image>');z.write(r/'assets/brand_mark.png','data/brand_mark.png');z.write(r/'assets/client_source.png','data/background.png');z.write(r/'assets/client_source.png','mergedimage.png')
 with (r/'client_release_matrix.csv').open('w',encoding='utf-8',newline='') as f:w=csv.writer(f);w.writerow(['source_id','campaign','width','height','status']);w.writerows([['C-ALPHA','Autumn launch',640,360,'CURRENT'],['C-OLD','Summer launch',600,340,'SUPERSEDED'],['C-THUMB','Autumn thumbnail',320,180,'CURRENT']])
 with (r/'server_release_matrix.csv').open('w',encoding='utf-8',newline='') as f:w=csv.writer(f);w.writerow(['source_id','path','content']);w.writerows([['S-CONFIG','config/service.json','{"api_version":"v3","locale":"en-US"}\n'],['S-LICENSE','LICENSE.txt','Internal evaluation package license.\n'],['S-OLD','obsolete/legacy.txt','Do not ship.\n']])
 (r/'client_rules.txt').write_text('Export current Autumn launch artwork as client_banner.png at 640x360 and client_thumbnail.png at 320x180. Preserve RGB PNG, use the provided brand mark, and include selected current source IDs in the release record.\n',encoding='utf-8');(r/'server_rules.txt').write_text('Build server_package.zip containing config/service.json with api_version v3 and locale en-US plus LICENSE.txt. Exclude superseded sources. Include a SHA-256 manifest for every member.\n',encoding='utf-8');(r/'release_manifest.json').write_text(json.dumps({'revision':0,'client':{},'server':{},'qa_state':'DRAFT'},indent=2),encoding='utf-8');(r/'qa/events.jsonl').write_text('',encoding='utf-8')
 if a.start_service:
  log=(r/'service.log').open('ab',buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/'qa_service.py'),'--root',str(r)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(['google-chrome','http://127.0.0.1:18223/release'],start_new_session=True)
if __name__=='__main__':main()
