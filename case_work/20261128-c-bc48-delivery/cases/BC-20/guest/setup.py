from __future__ import annotations
import argparse,csv,html,subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZIP_STORED,ZipFile

ROWS=[("H1","Marketing",1,100000,"YES","ACTIVE"),("H1","Marketing",2,104000,"NO","ACTIVE"),("H1","Marketing",3,99000,"NO","WITHDRAWN"),("H1","R&D",1,200000,"YES","ACTIVE"),("H1","Operations",1,80000,"NO","ACTIVE"),("H1","Operations",1,80000,"NO","ACTIVE"),("H2","Marketing",1,90000,"NO","ACTIVE"),("H2","R&D",1,180000,"YES","ACTIVE"),("H2","Operations",1,95000,"NO","ACTIVE"),("H2","Operations",2,94000,"NO","WITHDRAWN")]
def cell(value="",kind="string",formula=None):
 if kind=="float":attr=f' office:value-type="float" office:value="{value}"';inner=""
 else:attr=' office:value-type="string"';inner=f"<text:p>{html.escape(str(value))}</text:p>" if value else ""
 if formula:attr+=f' table:formula="{formula}"'
 return f"<table:table-cell{attr}>{inner}</table:table-cell>"
def table(name,depts):
 rows=["<table:table-row>"+"".join(cell(x) for x in ["Department","Requested USD","Protected","Approved USD","Reduction USD"])+"</table:table-row>"]
 for d in depts:rows.append("<table:table-row>"+cell(d)+cell()+cell()+cell(0,"float","of:=0")+cell(0,"float","of:=0")+"</table:table-row>")
 rows.append("<table:table-row>"+cell("TOTAL")+cell(0,"float","of:=SUM([.B2:.B4])")+cell()+cell(0,"float","of:=SUM([.D2:.D4])")+cell(0,"float","of:=SUM([.E2:.E4])")+"</table:table-row>")
 return f'<table:table table:name="{name}">'+"".join(rows)+"</table:table>"
def odf(path):
 content='''<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:spreadsheet>'''+table("Budget_H1",["Marketing","R&D","Operations"])+table("Budget_H2",["Marketing","R&D","Operations"])+'''<table:table table:name="Summary"><table:table-row>'''+cell("Half")+cell("Approved USD")+"</table:table-row><table:table-row>"+cell("H1")+cell(0,"float","of:=[Budget_H1.D5]")+"</table:table-row><table:table-row>"+cell("H2")+cell(0,"float","of:=[Budget_H2.D5]")+"</table:table-row><table:table-row>"+cell("FY Total")+cell(0,"float","of:=SUM([.B2:.B3])")+"</table:table-row></table:table></office:spreadsheet></office:body></office:document-content>"
 with ZipFile(path,"w") as z:z.writestr("mimetype","application/vnd.oasis.opendocument.spreadsheet",compress_type=ZIP_STORED);z.writestr("content.xml",content,compress_type=ZIP_DEFLATED);z.writestr("styles.xml",'<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:styles/><office:automatic-styles/><office:master-styles/></office:document-styles>');z.writestr("META-INF/manifest.xml",'<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
def pdf(path):
 lines=["Q4 OPERATING BUDGET RULES","Latest ACTIVE request revision per department is authoritative.","Protected YES rows retain 100 percent; other rows retain 96 percent.","Exclude WITHDRAWN requests and duplicate identical request IDs.","Approved equals rounded requested amount times retention rate; reduction equals requested minus approved.","Export the half-year sheet to PDF and a summary JSON."]
 stream="BT /F1 10 Tf 48 748 Td "+" ET BT /F1 10 Tf 48 ".join(f"{748-i*18} Td ({line}) Tj" for i,line in enumerate(lines))+" ET";data=stream.encode("ascii");objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(data)).encode()+b" >>\nstream\n"+data+b"\nendstream"];raw=bytearray(b"%PDF-1.4\n");offsets=[0]
 for i,obj in enumerate(objects,1):offsets.append(len(raw));raw.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
 xref=len(raw);raw.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode());raw.extend(b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets[1:]));raw.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode());path.write_bytes(bytes(raw))
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--open-calc",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"budget_lab";(root/"out").mkdir(parents=True,exist_ok=True);odf(root/"budget_master.ods")
 with (root/"budget_requests.csv").open("w",encoding="utf-8",newline="") as f:w=csv.writer(f);w.writerow(["half","department","revision","request_usd","protected","status","request_id"]);w.writerows([*r,f"{r[0]}-{r[1]}-{r[2]}"] for r in ROWS)
 pdf(root/"budget_rules.pdf")
 if a.open_calc:subprocess.Popen(["libreoffice","--calc",str(root/"budget_master.ods")],start_new_session=True)
if __name__=="__main__":main()
