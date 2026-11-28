from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
def pdf(path):
 d=b"BT /F1 12 Tf 60 740 Td (SERVICE LAB HANDOFF) Tj 0 -24 Td (Configure both interfaces and validate the active snapshot after restart.) Tj ET";objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(d)).encode()+b" >>\nstream\n"+d+b"\nendstream"];o=bytearray(b"%PDF-1.4\n");off=[0]
 for i,x in enumerate(objs,1):off.append(len(o));o.extend(f"{i} 0 obj\n".encode()+x+b"\nendobj\n")
 pos=len(o);o.extend(f"xref\n0 {len(off)}\n0000000000 65535 f \n".encode());[o.extend(f"{x:010d} 00000 n \n".encode()) for x in off[1:]];o.extend(f"trailer\n<< /Size {len(off)} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n".encode());path.write_bytes(o)
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();base=Path(a.workspace).expanduser().resolve()/"service_lab";repo=base/"repo";(repo/"services").mkdir(parents=True,exist_ok=True);(base/"out").mkdir(exist_ok=True)
 (repo/".env").write_text("RELEASE_ENV=staging\nSERVICE_A_LIMIT=0\nSERVICE_B_LIMIT=0\n",encoding="utf-8");(repo/"services/settings.json").write_text(json.dumps({"frontline":{"route":"","limit":0,"auth":""},"catalog":{"route":"","timeout_s":0,"fallback":""}},indent=2)+"\n",encoding="utf-8");(repo/"README.md").write_text("# Service Lab\nLocal configuration exercise. Use the service status page after restart.\n",encoding="utf-8")
 subprocess.run(["git","init"],cwd=repo,check=True,stdout=subprocess.DEVNULL);subprocess.run(["git","branch","-M","main"],cwd=repo,check=True,stdout=subprocess.DEVNULL);subprocess.run(["git","config","user.name","Service Lab Agent"],cwd=repo,check=True);subprocess.run(["git","config","user.email","service-lab@example.invalid"],cwd=repo,check=True);subprocess.run(["git","add","."],cwd=repo,check=True);subprocess.run(["git","commit","-m","Seed service lab"],cwd=repo,check=True,stdout=subprocess.DEVNULL)
 (base/"restart_receipts.jsonl").touch(exist_ok=True)
 pdf(base/"service_requirements.pdf")
 if a.start_service:
  log=(base/"service.log").open("ab",buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/"service.py"),"--repo",str(repo),"--root",str(base)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18115/"],start_new_session=True)
if __name__=="__main__":main()
