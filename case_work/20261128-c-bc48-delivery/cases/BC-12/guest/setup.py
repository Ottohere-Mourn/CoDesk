from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw

ASSETS={
 "a_banner_01.png":(1600,900,(38,96,160)),"a_banner_02.png":(1920,1080,(27,130,118)),"a_banner_square.png":(1000,1000,(180,115,35)),"a_banner_low.png":(640,360,(90,90,150)),
 "b_product_01.png":(1200,1500,(133,70,138)),"b_product_02.png":(1200,1500,(42,138,132)),"b_product_square.png":(1000,1000,(166,104,63)),"b_product_low.png":(600,750,(85,110,165))}
def pdf(path,lines):
 text=("BT /F1 10 Tf 48 748 Td "+" ".join(f"({s}) Tj 0 -16 Td" for s in lines)+" ET").encode("ascii","replace");objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(text)).encode()+b" >>\nstream\n"+text+b"\nendstream"];o=bytearray(b"%PDF-1.4\n");offs=[0]
 for i,x in enumerate(objs,1):offs.append(len(o));o.extend(f"{i} 0 obj\n".encode()+x+b"\nendobj\n")
 x=len(o);o.extend(f"xref\n0 {len(offs)}\n0000000000 65535 f \n".encode());[o.extend(f"{n:010d} 00000 n \n".encode()) for n in offs[1:]];o.extend(f"trailer\n<< /Size {len(offs)} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode());path.write_bytes(o)
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"asset_qa";src=root/"source";out=root/"out";src.mkdir(parents=True,exist_ok=True);out.mkdir(exist_ok=True)
 for name,(w,h,color) in ASSETS.items():
  image=Image.new("RGB",(w,h),color);d=ImageDraw.Draw(image);d.rectangle((w//8,h//8,7*w//8,7*h//8),outline=(240,240,240),width=max(2,min(w,h)//80));d.text((w//12,h//2),name,fill=(255,255,255));image.save(src/name)
 (src/"a_banner_broken.png").write_bytes(b"not-a-png: truncated campaign source")
 (src/"b_product_broken.png").write_bytes(b"not-a-png: truncated product source")
 (root/"asset_manifest.yaml").write_text(json.dumps({"schema":"bc12-asset-manifest/v1","revision":1,"assets":[],"excluded":[]},indent=2)+"\n",encoding="utf-8")
 (root/"qa_receipts.json").write_text(json.dumps({"receipts":{}},indent=2)+"\n",encoding="utf-8")
 (root/"qa_events.jsonl").write_text("",encoding="utf-8")
 pdf(root/"image_rules.pdf",["IMAGE PIPELINE AND RELEASE RULES","A banner set: exactly two campaign sources, each exported PNG 1280 x 720 with watermark Q4 LAUNCH.","B product set: exactly two product sources, each exported PNG 800 x 1000 with watermark PRODUCT READY.","Use source images at least 1200 pixels on the longer side and with the required source aspect ratio.","Classify every source file as exported or excluded; exclusions require a concise reason.","Corrupt, undersized, or wrong-aspect sources must not be exported.","Submit to the local QA desk, correct each rejection, and resubmit the updated manifest.","The release is ready only after the QA desk records a passing receipt for the correct manifest revision."])
 if a.start_service:
  log=(root/"qa_service.log").open("ab",buffering=0);proc=subprocess.Popen([sys.executable,str(Path(a.source_dir)/"qa_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18112/"],start_new_session=True)
if __name__=="__main__":main()
