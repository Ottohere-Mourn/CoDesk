from __future__ import annotations
import argparse,csv,json
from pathlib import Path

REVENUE=[
 ["INV-1001","2026-10-02","North",1000,"POSTED"],["INV-1002","2026-10-08","East",500,"POSTED"],
 ["INV-1002","2026-10-08","East",500,"POSTED"],["INV-1003","2026-11-14","South",1200,"POSTED"],
 ["INV-1004","2026-11-20","North",250,"VOID"],["INV-1005","2026-12-03","North",700,"POSTED"],
 ["REF-1005","2026-12-17","North",-100,"REFUND"],["INV-0999","2026-09-30","South",900,"POSTED"],
 ["INV-1006","2026-12-31","East",300,"TEST"]]
EVENTS=[
 ["E01","u1","signup","2026-10-01","VALID"],["E02","u2","signup","2026-10-10","VALID"],
 ["E03","u3","signup","2026-10-20","VALID"],["E04","u4","signup","2026-11-01","VALID"],
 ["E05","u5","signup","2026-10-31","VALID"],["E06","u5","signup","2026-11-02","VALID"],
 ["E07","u6","signup","2026-10-15","TEST"],["E08","u1","session","2026-10-15","VALID"],
 ["E09","u1","session","2026-11-05","VALID"],["E10","u2","session","2026-11-05","VALID"],
 ["E11","u2","session","2026-11-20","VALID"],["E12","u3","session","2026-12-01","VALID"],
 ["E13","u5","session","2026-11-14","VALID"],["E14","u4","session","2026-11-20","VALID"],
 ["E15","u1","session","2026-10-15","VALID"]]
def write_pdf(path,lines):
 content=("BT /F1 10 Tf 48 748 Td "+" ".join(f"({s}) Tj 0 -16 Td" for s in lines)+" ET").encode("ascii","replace")
 objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream"]
 out=bytearray(b"%PDF-1.4\n");offs=[0]
 for i,obj in enumerate(objs,1):offs.append(len(out));out.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
 xref=len(out);out.extend(f"xref\n0 {len(offs)}\n0000000000 65535 f \n".encode())
 for n in offs[1:]:out.extend(f"{n:010d} 00000 n \n".encode())
 out.extend(f"trailer\n<< /Size {len(offs)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode());path.write_bytes(out)
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"kernel_lab";root.mkdir(parents=True,exist_ok=True);(root/"out").mkdir(exist_ok=True)
 for name,header,rows in [("revenue_source.csv",["invoice_id","invoice_date","region","amount_usd","status"],REVENUE),("product_events.csv",["event_id","user_id","event_type","event_date","status"],EVENTS)]:
  with (root/name).open("w",encoding="utf-8",newline="") as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
 (root/"kernel_events.jsonl").touch(exist_ok=True)
 (root/"q4_pipeline.json").write_text(json.dumps({"format":"bc11-pipeline/v1","cells":[]},indent=2)+"\n",encoding="utf-8")
 write_pdf(root/"analysis_rules.pdf",["Q4 ANALYSIS RULES","Revenue: include valid Q4 2026 POSTED invoices and REFUND rows; exclude TEST and VOID.","Deduplicate POSTED invoices by invoice_id; a duplicate invoice contributes once.","Refund amounts are negative and reduce regional and total revenue.","Retention cohort: first VALID signup during October 2026, one row per user.","M1 active window: day 14 through day 30 inclusive after first signup.","M2 active window: day 31 through day 60 inclusive after first signup.","Count a user once in a window regardless of duplicate sessions. Exclude TEST rows."])
 if a.start_service:
  import subprocess,sys
  log=(root/"kernel_service.log").open("ab",buffering=0);proc=subprocess.Popen([sys.executable,str(Path(a.source_dir)/"kernel_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:
  import subprocess
  subprocess.Popen(["google-chrome","http://127.0.0.1:18111/"],start_new_session=True)
if __name__=="__main__":main()
