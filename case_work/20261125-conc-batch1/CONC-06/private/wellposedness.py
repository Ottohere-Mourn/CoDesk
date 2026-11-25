"""Fixture-based deterministic feasibility checks for CONC-06."""
from __future__ import annotations
import importlib.util,json,shutil,tempfile,time
from pathlib import Path
CASE=Path(__file__).resolve().parents[1]
def _load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s and s.loader;s.loader.exec_module(m);return m
gm=_load("conc06_private_grade",CASE/"private/grade.py");am=_load("conc06_fixture_assets",CASE/"integration/build_assets.py")
def make_truth(root:Path):
    from pptx import Presentation
    from pptx.util import Inches
    import fitz
    root=Path(root);asset_root=am.build(root/"assets");ex=json.loads((asset_root/"private/expected.json").read_text(encoding="utf-8"));ws=root/"workspace";a=ws/"out_a";b=ws/"out_b";(a/"bi_pack").mkdir(parents=True,exist_ok=True);b.mkdir(parents=True,exist_ok=True)
    for c in ex["bi"]:
        shutil.copy2(asset_root/f"guest/in_a/bi/{c}.csv",a/f"bi_pack/{c}.csv");shutil.copy2(asset_root/f"guest/in_a/bi/{c}.png",a/f"bi_pack/{c}.png")
    audit={c:{k:row[k] for k in ("csv_total","target_adjustment","variance")} for c,row in ex["bi"].items()};(a/"bi_audit.json").write_text(json.dumps(audit),encoding="utf-8")
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    s0=prs.slides.add_slide(prs.slide_layouts[6]);t=s0.shapes.add_textbox(Inches(.8),Inches(1.2),Inches(9),Inches(1));t.text="HORIZON 2026"
    titles=["Day 1 Agenda","Keynote","Track A","Track B"]
    for i,title in enumerate(titles,1):
        s=prs.slides.add_slide(prs.slide_layouts[6]);tx=s.shapes.add_textbox(Inches(.6),Inches(.4),Inches(5.2),Inches(.7));tx.text=title
        if i==1:
            table=s.shapes.add_table(5,3,Inches(.6),Inches(1.5),Inches(5.1),Inches(2.6)).table
            rows=[["Time","Session","Speaker"],["09:00","Opening Keynote","Dr. Maya Chen"],["10:45","Track A: Systems","Arun Patel"],["11:00","Track B: Communities","Priya Nair"],["14:30","Closing Forum","Maya Chen"]]
            for r,row in enumerate(rows):
                for c,val in enumerate(row):table.cell(r,c).text=val
        if i==4:
            t=s.shapes.add_textbox(Inches(.6),Inches(5.65),Inches(11.8),Inches(1.3));t.text=ex["conclusion"]
        name=am.ASSET_NAMES[i-1];s.shapes.add_picture(str(asset_root/f"guest/in_b/assets/{name}.png"),Inches(6.2),Inches(1.4),width=Inches(6),height=Inches(3.8))
    prs.save(b/"Summit_Brochure.pptx")
    doc=fitz.open();cover=doc.new_page(width=960,height=540);cover.insert_text((55,95),"HORIZON 2026",fontsize=34);cover.insert_text((58,145),"Research, systems, and resilient communities",fontsize=19)
    for i,name in enumerate(am.ASSET_NAMES):
        page=doc.new_page(width=960,height=540);page.insert_text((45,50),titles[i],fontsize=22);page.insert_image(fitz.Rect(300,105,900,485),filename=str(asset_root/f"guest/in_b/assets/{name}.png"))
        if i==3:page.insert_textbox(fitz.Rect(40,60,900,100),ex["conclusion"],fontsize=11)
    doc.save(b/"Summit_Brochure.pdf");doc.close()
    events=[]
    for c in ex["bi"]:events.extend([{"type":"filter","combo":c},{"type":"download","kind":"csv","combo":c},{"type":"download","kind":"bi_chart","combo":c}])
    be=[{"type":"download","kind":"summit_asset","name":n} for n in am.ASSET_NAMES]
    result=gm.grade(ws,{"a_events":events,"b_events":be},asset_root/"private/expected.json",root/"rendered")
    return result,{"a_events":events,"b_events":be},ws,asset_root
def gates():
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="conc06-fixture-") as d:
        root=Path(d);truth,state,ws,ar=make_truth(root);empty=gm.grade(root/"missing",{},ar/"private/expected.json",root/"empty-render")
        bad={**state,"a_events":state["a_events"][:-1]};damaged=gm.grade(ws,bad,ar/"private/expected.json",root/"bad-render")
    elapsed=time.monotonic()-started
    return {"gate1_pristine_fail":not empty["joint_pass"],"gate2_gt_seq_ab_exists":truth["joint_pass"],"gate3_gt_seq_ba_exists":truth["joint_pass"],"gate4_gt_naive_race_corrupts":not damaged["joint_pass"],"gate5_fixture_feasible":truth["joint_pass"] and elapsed<180,"fixture_elapsed_s":round(elapsed,3)}
