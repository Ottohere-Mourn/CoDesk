from __future__ import annotations
import argparse, csv, sqlite3, zipfile
from pathlib import Path

def pdf(path: Path, lines: list[str]) -> None:
    stream=("BT\n/F1 10 Tf\n48 748 Td\n"+"\n".join(("0 -14 Td\n" if i else "")+f"({s.replace('(','[').replace(')',']')}) Tj" for i,s in enumerate(lines))+"\nET").encode("ascii","replace")
    objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream"]
    out=bytearray(b"%PDF-1.4\n"); offsets=[0]
    for i,obj in enumerate(objs,1): offsets.append(len(out));out.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
    x=len(out);out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode());[out.extend(f"{n:010d} 00000 n \n".encode()) for n in offsets[1:]];out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode());path.write_bytes(out)

def make_odp(path: Path) -> None:
    content='''<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.2"><office:body><office:presentation>'''+''.join(f'<draw:page draw:name="{name}" draw:style-name="dp1"><draw:frame draw:style-name="gr1" draw:text-style-name="P1" svg:x="1cm" svg:y="1cm" svg:width="24cm" svg:height="5cm" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"><draw:text-box><text:p>{title}</text:p><text:p>{body}</text:p></draw:text-box></draw:frame></draw:page>' for name,title,body in [("Cover","Q4 Board Review","Finance and Product Performance"),("Finance","Regional Revenue","Finance section awaiting analysis"),("Finance Detail","Margin Bridge","Financial assumptions and methodology"),("Product","Cohort Retention","Product section awaiting analysis"),("Product Detail","Latency and Adoption","Product methodology and observations")])+'''</office:presentation></office:body></office:document-content>'''
    manifest='''<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.presentation"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    styles='''<?xml version="1.0" encoding="UTF-8"?><office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:styles/><office:automatic-styles/><office:master-styles/></office:document-styles>'''
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("mimetype","application/vnd.oasis.opendocument.presentation",compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml",content);z.writestr("styles.xml",styles);z.writestr("META-INF/manifest.xml",manifest)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-dir',required=True);ap.add_argument('--workspace',required=True);ap.add_argument('--open-impress',action='store_true');a=ap.parse_args()
    root=Path(a.workspace).expanduser().resolve()/"boardroom";root.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(root/"transactions.db");db.execute("CREATE TABLE fx(currency TEXT PRIMARY KEY,usd REAL)");db.executemany("INSERT INTO fx VALUES(?,?)",[("USD",1.0),("EUR",1.08),("GBP",1.27),("CAD",.74)])
    db.execute("CREATE TABLE transactions(txn_id TEXT,region TEXT,currency TEXT,amount REAL,cost REAL,status TEXT,source TEXT)")
    for i in range(1,81):
        region=("North","South","East","West")[(i-1)%4];currency=("USD","EUR","GBP","CAD")[(i-1)%4]
        status="SETTLED" if i%11 not in (0,1) else "REVERSED" if i%11==0 else "TEST"
        amount=800+i*23.5;cost=amount*(.42+(.01*(i%7)))
        db.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?)",(f"TX-{i:04d}",region,currency,amount,cost,status,"ERP"))
        if i in (17,43): db.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?)",(f"TX-{i:04d}-DUP",region,currency,amount,cost,"SETTLED","DUPLICATE_FEED"))
    db.commit();db.close()
    with (root/"telemetry.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["account_id","cohort_month","month_index","active","latency_ms","record_type"])
        for u in range(1,61):
            cohort=f"2026-{(u%3)+7:02d}";size=(u%4)+1
            for m in range(0,4):
                w.writerow([f"AC-{u:03d}",cohort,m,1 if (u+m)%5 else 0,180+((u*29+m*53)%420),"production"])
        w.writerow(["AC-TEST","2026-08",0,1,9000,"synthetic"]);w.writerow(["AC-001","2026-08",0,1,210,"duplicate"])
    make_odp(root/"q4_board_deck.odp")
    pdf(root/"finance_rules.pdf",["Q4 FINANCE METHOD","Convert settled amounts to USD using fx.usd.","Exclude REVERSED and TEST transactions and source DUPLICATE_FEED.","Revenue is sum(amount * USD rate). Gross margin percent is (revenue - cost) / revenue * 100.","Round currency to 2 decimals and margin to 2 decimals.","Provide the four region totals and a total row."])
    pdf(root/"product_rules.pdf",["PRODUCT COHORT METHOD","Use production telemetry only; remove duplicate account/cohort/month rows.","Cohort retention is active accounts at month N divided by cohort size, percent.","Report month 1 and month 3 retention for each cohort and the account-weighted overall rate.","Latency uses production rows only; report median and P95 in milliseconds, rounded to 1 decimal."])
    if a.open_impress:
        import subprocess;subprocess.Popen(["libreoffice","--impress",str(root/"q4_board_deck.odp")],start_new_session=True)
if __name__=='__main__':main()
