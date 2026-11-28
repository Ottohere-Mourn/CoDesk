from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dispatch_service import init_db


def write_rules(path):
    lines=["NORTH DEPOT WAREHOUSE RULES", "Inbound: eligible orders have damage_flag=0 and temperature_c from 2.0 through 8.0 inclusive.",
           "Use the listed primary bin except when the Phase 1 response reports BIN_FULL.", "BIN_FULL overflow route: COLD-OV1 for cold-chain orders.",
           "Outbound: release only if credit_hold=0 and qa_status=PASS.", "For CUSTOMS_MISMATCH, consult customs_overrides.csv and apply the matching approved code.",
           "Use the current phase token for final commit; never reuse a token after commit.", "Only change orders selected for the requested workflow."]
    def esc(text): return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream=("BT\n/F1 10 Tf\n48 748 Td\n"+"\n".join(("0 -14 Td\n" if i else "")+f"({esc(line)}) Tj" for i,line in enumerate(lines))+"\nET").encode("ascii")
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream"]
    out=bytearray(b"%PDF-1.4\n");offs=[0]
    for i,obj in enumerate(objects,1):offs.append(len(out));out.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
    xref=len(out);out.extend(f"xref\n0 {len(offs)}\n0000000000 65535 f \n".encode())
    for off in offs[1:]:out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offs)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode());path.write_bytes(out)


def main():
    p=argparse.ArgumentParser();p.add_argument("--source-dir",required=True);p.add_argument("--workspace",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args()
    root=Path(a.workspace).expanduser().resolve()/"dispatch";root.mkdir(parents=True,exist_ok=True)
    inbound_targets={"IN-1002":("BIN-A1",0,4.2,40,"COLD"),"IN-1005":("BIN-A2",0,3.5,24,"AMBIENT"),
                     "IN-1009":("BIN-B1",0,5.1,36,"AMBIENT"),"IN-1013":("BIN-B2",0,4.0,18,"COLD"),
                     "IN-1018":("BIN-C1",0,3.7,30,"COLD"),"IN-1024":("BIN-C2",0,6.0,28,"COLD")}
    with (root/"inbound_manifest.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["order_id","damage_flag","temperature_c","qty","primary_bin","storage_class"])
        for i in range(1,31):
            oid=f"IN-{1000+i}"
            if oid in inbound_targets:bin_code,damage,temp,qty,storage=inbound_targets[oid]
            else:bin_code,damage,temp,qty,storage=f"BIN-N{i:02d}",(1 if i%2 else 0),(3.5 if i%2 else 10.5),12+i,("COLD" if i%3==0 else "AMBIENT")
            w.writerow([oid,damage,temp,qty,bin_code,storage])
    with (root/"bins.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["bin_code","storage_class","capacity","occupied","overflow"])
        for bin_code,storage in [(r[0],r[4]) for r in inbound_targets.values()]:
            congested=bin_code in {"BIN-C1","BIN-C2"}
            w.writerow([bin_code,storage,60 if congested else 200,50 if congested else 0,0])
        for i in range(1,31):
            oid=f"IN-{1000+i}"
            if oid not in inbound_targets:w.writerow([f"BIN-N{i:02d}","COLD" if i%3==0 else "AMBIENT",200,0,0])
        w.writerow(["COLD-OV1","COLD",100,0,1])
    with (root/"outbound_orders.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["order_id","credit_hold","qa_status","customs_code"])
        for i in range(1,31):
            oid=f"OUT-{2000+i}";eligible=oid in {"OUT-2001","OUT-2004","OUT-2007","OUT-2011","OUT-2015","OUT-2020"};hold=0 if eligible else (1 if i%2 else 0);qa="PASS" if eligible or hold else "FAIL"
            w.writerow([oid,hold,qa,"CUS-MISMATCH" if oid in {"OUT-2015","OUT-2020"} else "CUS-OK"])
    with (root/"customs_overrides.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["order_id","override_code","approval_reason"])
        w.writerows([["OUT-2015","CUS-OVR-7A","Verified origin annex"],["OUT-2020","CUS-OVR-9C","Broker correction accepted"]])
    write_rules(root/"warehouse_rules.pdf")
    init_db(root/"rooms.db",root)
    if a.start_service:
        log=open(root/"dispatch_service.log","ab",buffering=0)
        subprocess.Popen([sys.executable,str(Path(a.source_dir)/"dispatch_service.py"),"--workspace",str(a.workspace),"--port","8092"],cwd=str(Path(a.source_dir)),stdout=log,stderr=log,start_new_session=True)
        for _ in range(50):
            try:urllib.request.urlopen("http://127.0.0.1:8092/api/state",timeout=.2).read();break
            except Exception:time.sleep(.1)
    if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:8092/"],start_new_session=True)


if __name__=="__main__":main()
