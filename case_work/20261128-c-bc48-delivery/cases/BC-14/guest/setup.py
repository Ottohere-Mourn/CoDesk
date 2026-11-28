from __future__ import annotations
import argparse,csv,json,subprocess,sys
from pathlib import Path
CARDS=[
 {"id":"FL-104","queue":"frontline","status":"TRIAGED","owner":"","severity":"high","age_hours":31,"summary":"Checkout retries exceed normal limit","resolution":"","sla":"unassigned"},
 {"id":"FL-108","queue":"frontline","status":"TRIAGED","owner":"","severity":"medium","age_hours":8,"summary":"Receipt email delayed after payment","resolution":"","sla":"unassigned"},
 {"id":"FL-112","queue":"frontline","status":"TRIAGED","owner":"","severity":"high","age_hours":53,"summary":"Regional tax rounding mismatch","resolution":"","sla":"unassigned"},
 {"id":"BE-203","queue":"backend","status":"TRIAGED","owner":"","severity":"high","age_hours":18,"summary":"Event consumer lag at peak load","resolution":"","sla":"unassigned"},
 {"id":"BE-207","queue":"backend","status":"TRIAGED","owner":"","severity":"medium","age_hours":12,"summary":"Warehouse snapshot checksum drift","resolution":"","sla":"unassigned"},
 {"id":"BE-211","queue":"backend","status":"TRIAGED","owner":"","severity":"high","age_hours":42,"summary":"Token refresh loop on worker pool","resolution":"","sla":"unassigned"},
 {"id":"FL-119","queue":"frontline","status":"DUPLICATE","owner":"","severity":"low","age_hours":10,"summary":"Duplicate of FL-108","resolution":"","sla":"excluded"},
 {"id":"BE-219","queue":"backend","status":"CANCELLED","owner":"","severity":"low","age_hours":7,"summary":"Cancelled migration dry run","resolution":"","sla":"excluded"}]
def pdf(path,lines):
 text=("BT /F1 10 Tf 48 748 Td "+" ".join(f"({x}) Tj 0 -16 Td" for x in lines)+" ET").encode("ascii","replace");o=bytearray(b"%PDF-1.4\n");objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(text)).encode()+b" >>\nstream\n"+text+b"\nendstream"];off=[0]
 for i,x in enumerate(objs,1):off.append(len(o));o.extend(f"{i} 0 obj\n".encode()+x+b"\nendobj\n")
 pos=len(o);o.extend(f"xref\n0 {len(off)}\n0000000000 65535 f \n".encode());[o.extend(f"{n:010d} 00000 n \n".encode()) for n in off[1:]];o.extend(f"trailer\n<< /Size {len(off)} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n".encode());path.write_bytes(o)
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"status_board";root.mkdir(parents=True,exist_ok=True)
 (root/"board_state.json").write_text(json.dumps({"revision":0,"cards":CARDS},indent=2)+"\n",encoding="utf-8")
 with (root/"work_items.csv").open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(CARDS[0]));w.writeheader();w.writerows(CARDS)
 pdf(root/"sla_policy.pdf",["WORK QUEUE POLICY","High severity: P1; medium severity: P2.","Age greater than 36 hours is overdue; 18 to 36 hours is at risk; below 18 hours is within SLA.","Do not modify DUPLICATE or CANCELLED cards.","Frontline: FL-104 in progress/Maya Chen; FL-108 resolved/Jordan Lee; FL-112 escalated/Sam Rivera.","Backend: BE-203 in review/Platform On-Call; BE-207 resolved/Data Ops; BE-211 in progress/Runtime Team.","Each active card must contain a concise resolution or validation note derived from its summary.","Save the entire current board state after editing. Export a queue-specific JSON containing the exact changed card set."])
 if a.start_service:
  log=(root/"board_service.log").open("ab",buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/"board_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18114/"],start_new_session=True)
if __name__=="__main__":main()
