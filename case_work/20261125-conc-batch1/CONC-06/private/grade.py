"""Private 26-check deterministic oracle for CONC-06."""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path

HERE=Path(__file__).resolve().parent
def _sha(path):
    try:return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:return ""
def _json(path):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError):return None
def _expected(path=None):
    p=Path(path) if path else Path(os.environ.get("PARAGUI_TASK_ASSETS",""))/"CONC-06/private/expected.json"
    if not p.is_file():p=HERE/"expected.json"
    try:return json.loads(p.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return {"bi":{},"assets":{}}
def _a(workspace,state,expected):
    out=Path(workspace)/"out_a";pack=out/"bi_pack";audit=_json(out/"bi_audit.json");audit=audit if isinstance(audit,dict) else {}
    combos=("NA-Q3","EU-Q3","APAC-Q4","LATAM-Q4");checks=[]
    checks.append(set(audit)==set(combos))
    for c in combos:
        row=audit.get(c,{});truth=expected["bi"].get(c,{})
        checks.append(isinstance(row,dict) and all(isinstance(row.get(k),(int,float)) and abs(float(row[k])-float(truth.get(k,1e99)))<1e-2 for k in ("csv_total","target_adjustment","variance")))
    for c in combos:checks.append(_sha(pack/f"{c}.csv")==expected["bi"].get(c,{}).get("csv_sha256","!missing"))
    checks.append(all(_sha(pack/f"{c}.png")==expected["bi"].get(c,{}).get("png_sha256","!missing") for c in combos[:2]))
    checks.append(_sha(pack/"APAC-Q4.png")==expected["bi"].get("APAC-Q4",{}).get("png_sha256","!missing"))
    checks.append(_sha(pack/"LATAM-Q4.png")==expected["bi"].get("LATAM-Q4",{}).get("png_sha256","!missing"))
    events=state.get("a_events",[]);downloads=[e for e in events if e.get("type")=="download"]
    exported={(e.get("kind"),e.get("combo")) for e in downloads}
    selection={e.get("combo") for e in events if e.get("type")=="filter"}
    no_asset_mix=not any(_sha(p)==v.get("sha256") for p in pack.glob("*.png") for v in expected.get("assets",{}).values())
    checks.append(no_asset_mix and all((k,c) in exported for c in combos for k in ("csv","bi_chart")) and set(combos)<=selection)
    return checks

def _b(workspace,expected,render_dir):
    out=Path(workspace)/"out_b";pptx=out/"Summit_Brochure.pptx";pdf=out/"Summit_Brochure.pdf";checks=[]
    try:
        from pptx import Presentation
        prs=Presentation(str(pptx));slides=list(prs.slides);valid=len(slides)==5
    except Exception:slides=[];valid=False
    checks.append(valid)
    agenda=expected.get("agenda",{})
    if valid:
        try:
            table=next(s.table for s in slides[1].shapes if s.has_table)
            vals={"keynote_time":table.cell(1,0).text,"keynote_speaker":table.cell(1,2).text,"track_a_time":table.cell(2,0).text,"track_b_speaker":table.cell(3,2).text}
            checks.extend(vals.get(k)==v for k,v in agenda.items())
        except Exception:checks.extend([False]*4)
    else:checks.extend([False]*4)
    asset_order=("Summit_Keynote","Summit_TrackA","Summit_TrackB","Summit_Roadmap")
    image_shapes={}
    if valid:
        for i,s in enumerate(slides):
            image_shapes[i]=[sh for sh in s.shapes if getattr(sh,"shape_type",None)==13]
    for i,name in enumerate(asset_order,1):
        want=expected.get("assets",{}).get(name,{}).get("sha256")
        imgs=image_shapes.get(i,[])
        checks.append(len(imgs)>=1 and any(hashlib.sha256(sh.image.blob).hexdigest()==want for sh in imgs))
    # All four required images must be in-slide and avoid nonempty text shapes.
    safe=valid
    if valid:
        for i in range(1,5):
            imgs=image_shapes.get(i,[]);others=[s for s in slides[i].shapes if getattr(s,"has_text_frame",False) and s.text_frame.text.strip()]
            for im in imgs:
                safe &= im.left>=0 and im.top>=0 and im.left+im.width<=prs.slide_width and im.top+im.height<=prs.slide_height
                for tx in others:
                    overlap=max(0,min(im.left+im.width,tx.left+tx.width)-max(im.left,tx.left))*max(0,min(im.top+im.height,tx.top+tx.height)-max(im.top,tx.top))
                    safe &= overlap==0
    checks.append(bool(safe))
    conclusion=expected.get("conclusion","")
    if valid:
        try:
            slide5="\n".join(sh.text_frame.text for sh in slides[4].shapes if getattr(sh,"has_text_frame",False))
            statement=conclusion in slide5 and not any((sh.top+sh.height)>prs.slide_height for sh in slides[4].shapes if getattr(sh,"has_text_frame",False) and conclusion in sh.text_frame.text)
        except Exception:statement=False
    else:statement=False
    checks.append(statement)
    try:
        import fitz
        doc=fitz.open(pdf);pdf_ok=len(doc)==5
    except Exception:doc=None;pdf_ok=False
    checks.append(pdf_ok)
    render_ok=pdf_ok
    if pdf_ok:
        render_dir=Path(render_dir);render_dir.mkdir(parents=True,exist_ok=True)
        palette=[tuple(bytes.fromhex(expected["assets"][n]["color"].lstrip("#"))) for n in asset_order]
        for i,page in enumerate(doc):
            pix=page.get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False);p=render_dir/f"page-{i+1}.png";pix.save(p)
            try:
                from PIL import Image
                im=Image.open(p).convert("RGB");colors=set(im.getdata());color_ok=sum(colors.count(c) if hasattr(colors,"count") else 0 for c in palette)>0
                # Count target-color pixels without materializing all page pixels into output.
                hits=sum(1 for px in im.getdata() if px in palette)
                nonwhite=sum(1 for px in im.getdata() if min(px)<242)
                render_ok &= nonwhite>2000 and (i==0 or hits>80)
            except Exception:render_ok=False
        text="\n".join(p.get_text() for p in doc)
        render_ok &= "measurable collaboration" in text.lower()
        doc.close()
    checks.append(bool(render_ok))
    return checks

def grade(workspace,state=None,expected_path=None,render_dir=None):
    exp=_expected(expected_path);state=state or {};workspace=Path(workspace)
    a=_a(workspace,state,exp);b=_b(workspace,exp,render_dir or workspace/"rendered")
    return {"actor_a":sum(a)/13,"actor_b":sum(b)/13,"joint_pass":all(a) and all(b),"checks":{"actor_a":a,"actor_b":b},"flags":[*(f"A{i+1}" for i,x in enumerate(a) if not x),*(f"B{i+1}" for i,x in enumerate(b) if not x)]}
