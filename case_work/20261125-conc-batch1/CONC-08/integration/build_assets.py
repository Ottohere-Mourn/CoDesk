"""Build deterministic English source material for CONC-08."""
from __future__ import annotations

import csv, hashlib, json, os, random, shutil, string, subprocess, tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

CASE = Path(__file__).resolve().parents[1]
FX = {"USD": (1.0, 0.08), "EUR": (1.08, 0.10), "GBP": (1.27, 0.12)}
BLUE = "173B63"
LIGHT = "EAF1F7"


def _font(size=26, bold=False):
    for name in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            f = ImageFont.truetype(name, size)
            if bold:
                for alt in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                    try: return ImageFont.truetype(alt, size)
                    except OSError: pass
            return f
        except OSError: pass
    return ImageFont.load_default()


def _memo_png(path: Path, title: str, code: str, amount: float, currency: str, dept: str):
    im = Image.new("RGB", (1260, 760), "#f5f7fb")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((35, 35, 1225, 725), radius=20, fill="white", outline="#b9c7d8", width=3)
    d.rectangle((35, 35, 1225, 160), fill="#173b63")
    d.text((75, 65), title, fill="white", font=_font(38, True))
    d.text((80, 220), "Reference", fill="#536579", font=_font(25))
    d.text((80, 260), code, fill="#15283c", font=_font(37, True))
    d.text((80, 360), "Adjustment amount", fill="#536579", font=_font(25))
    d.text((80, 400), f"{currency} {amount:,.2f}", fill="#a73537", font=_font(43, True))
    d.text((80, 520), f"Department: {dept}", fill="#33465b", font=_font(28))
    d.text((80, 635), "Approved electronic close document", fill="#75869a", font=_font(21))
    im.save(path)


def _quarter_csv(path: Path, kind: str, q: int, rng: random.Random):
    rows = []
    for i in range(1, 8):
        currency = ("USD", "EUR", "GBP")[(i + q) % 3]
        if kind == "sales":
            rows.append({"invoice_id": f"INV-{q}{i:02d}", "quarter": f"Q{q}", "currency": currency,
                         "gross_amount": f"{rng.uniform(1800, 14500):.2f}", "status": "posted"})
        else:
            dept = ("Engineering", "Sales", "Operations", "People")[(i + q) % 4]
            rows.append({"employee_id": f"EMP-{q}{i:02d}", "quarter": f"Q{q}", "department": dept,
                         "currency": currency, "base_pay": f"{rng.uniform(2100, 8800):.2f}",
                         "overtime_hours": str((i * 3 + q) % 18), "overtime_multiplier": "2.00" if i % 5 == 0 else "1.50",
                         "status": "posted"})
    # Exact repeated records force deduplication; a separate negative credit remains valid.
    rows.insert(4, dict(rows[1]))
    rows.insert(8, dict(rows[5]))
    if kind == "sales":
        rows.append({"invoice_id": f"CR-{q}01", "quarter": f"Q{q}", "currency": "USD", "gross_amount": f"{-rng.uniform(75, 240):.2f}", "status": "return"})
        fields = ["invoice_id", "quarter", "currency", "gross_amount", "status"]
    else:
        # Duplicate a time card rather than the employee; correction row remains distinguishable.
        rows.append({"employee_id": f"OT-{q}01", "quarter": f"Q{q}", "department": "Operations", "currency": "USD",
                     "base_pay": "0.00", "overtime_hours": "-4", "overtime_multiplier": "1.50", "status": "correction"})
        fields = ["employee_id", "quarter", "department", "currency", "base_pay", "overtime_hours", "overtime_multiplier", "status"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    return rows


def _ledger_workbook(path: Path, truth: dict):
    """Use the bundled Artifact Tool authoring runtime for the XLSX output."""
    runtime=Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    node=runtime/"bin/node.exe" if os.name=="nt" else runtime/"bin/node"
    modules=runtime/"node_modules"
    if not node.is_file() or not modules.is_dir():raise RuntimeError("Bundled Artifact Tool runtime is unavailable")
    tmp=Path(tempfile.gettempdir())/"conc08-artifact-tool";tmp.mkdir(parents=True,exist_ok=True)
    modlink=tmp/"node_modules"
    if not modlink.exists():
        if os.name=="nt":
            ps=f"New-Item -ItemType Junction -Path '{modlink}' -Target '{modules}' | Out-Null"
            subprocess.run(["powershell","-NoProfile","-Command",ps],check=True,capture_output=True,text=True)
        else:modlink.symlink_to(modules,target_is_directory=True)
    script=Path(__file__).with_name("artifact_workbook.mjs");tmp_script=tmp/script.name;shutil.copy2(script,tmp_script)
    payload={"fx":truth["fx"],"hr_budgets":truth["hr_budgets"]};payload_path=tmp/"payload.json";payload_path.write_text(json.dumps(payload),encoding="utf-8")
    preview=Path(tempfile.gettempdir())/"conc08-workbook-previews";preview.mkdir(parents=True,exist_ok=True)
    run=subprocess.run([str(node),str(tmp_script),str(payload_path),str(path.resolve()),str(preview.resolve())],cwd=tmp,capture_output=True,text=True,timeout=180)
    if run.returncode or not path.is_file():raise RuntimeError(f"Artifact Tool workbook build failed: {run.stderr[-1500:]} {run.stdout[-1000:]}")


def _deck(path: Path, actor: str):
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    title="Finance Close | Annual Revenue" if actor=="a" else "People Close | Annual Cost"
    brief="Finance_Close" if actor=="a" else "HR_Close"
    pages=[(title,"FY2026 close review\nOwner: Corporate Finance" if actor=="a" else "FY2026 close review\nOwner: People Operations"),
           ("Executive summary","Replace with the verified annual total and quarter summary."),
           ("Quarterly trend","Insert the requested chart in the chart area; keep all labels readable."),
           ("Controls and sign-off","Document reconciliation, exceptions, source evidence, and reviewer sign-off.")]
    for idx,(heading,body) in enumerate(pages):
        slide=prs.slides.add_slide(prs.slide_layouts[6]);bg=slide.background.fill;bg.solid();bg.fore_color.rgb=RGBColor(245,248,252)
        tb=slide.shapes.add_textbox(Inches(.65),Inches(.38),Inches(12),Inches(.65));p=tb.text_frame.paragraphs[0];p.text=heading;p.font.size=Pt(28);p.font.bold=True;p.font.color.rgb=RGBColor(23,59,99)
        if idx==2:
            # Chart canvas intentionally sits below the header with clear margins.
            slot=slide.shapes.add_shape(1,Inches(.9),Inches(1.45),Inches(11.5),Inches(5.3));slot.fill.solid();slot.fill.fore_color.rgb=RGBColor(255,255,255);slot.line.color.rgb=RGBColor(190,204,219)
        else:
            box=slide.shapes.add_textbox(Inches(.9),Inches(1.45),Inches(11.4),Inches(4.8));tf=box.text_frame;tf.word_wrap=True
            for j,line in enumerate(body.split("\n")):
                p=tf.paragraphs[0] if j==0 else tf.add_paragraph();p.text=line;p.font.name="Arial";p.font.size=Pt(24 if idx==0 else 19);p.font.color.rgb=RGBColor(45,60,78);p.space_after=Pt(16)
        foot=slide.shapes.add_textbox(Inches(.7),Inches(7.05),Inches(12),Inches(.25));fp=foot.text_frame.paragraphs[0];fp.text=f"{brief} | Internal close pack | Page {idx+1} of 4";fp.font.size=Pt(9);fp.font.color.rgb=RGBColor(91,108,126)
    prs.save(path)


def build(destination: Path):
    dest=Path(destination);base=dest if dest.name=="CONC-08" else dest/"CONC-08";ga=base/"guest";private=base/"private"
    for d in (ga/"in_a/credit_memos",ga/"in_b/allowances",ga/"out_a",ga/"out_b",ga/"shared",private):d.mkdir(parents=True,exist_ok=True)
    rng=random.Random(20261125);rev_rows=[];raw_a=[];hr_rows=[];raw_b=[]
    for q in range(1,5):
        raw_a += _quarter_csv(ga/f"in_a/sales_q{q}.csv","sales",q,rng)
        raw_b += _quarter_csv(ga/f"in_b/payroll_q{q}.csv","payroll",q,rng)
    # Keep only distinct IDs while preserving the negative return row.
    sales=[];seen=set()
    for x in raw_a:
        if x["invoice_id"] not in seen:sales.append(x);seen.add(x["invoice_id"])
    for x in sales:
        rev_rows.append({"quarter":x["quarter"],"doc":x["invoice_id"],"currency":x["currency"],"gross":float(x["gross_amount"]),"adj":0.0,"note":x["status"]})
    memos=[]
    for i,q in enumerate(range(1,5),1):
        code="FIN-"+"-".join("".join(rng.choice(string.ascii_uppercase+string.digits) for _ in range(4)) for _ in range(3))
        currency=("EUR","GBP","USD","EUR")[i-1];amount=round(rng.uniform(105.50,880.25),2)
        item={"id":f"CM-{i:02d}","quarter":f"Q{q}","code":code,"currency":currency,"amount":amount,"category":("VAT","Excise","VAT","Sales Tax")[i-1]}
        memos.append(item);_memo_png(ga/f"in_a/credit_memos/{item['id']}.png",f"CREDIT MEMO {item['id']}",code,amount,currency,"Revenue Assurance");item["sha256"]=hashlib.sha256((ga/f"in_a/credit_memos/{item['id']}.png").read_bytes()).hexdigest()
        rev_rows.append({"quarter":f"Q{q}","doc":item["id"],"currency":currency,"gross":0.0,"adj":amount,"note":"credit memo"})
    people=[];seen=set()
    for x in raw_b:
        # Employee rows are distinct by employee id; identical duplicate clock cards are removed.
        key=(x["employee_id"],x["quarter"],x["base_pay"],x["overtime_hours"])
        if key not in seen:people.append(x);seen.add(key)
    for x in people:
        hr_rows.append({"quarter":x["quarter"],"employee":x["employee_id"],"department":x["department"],"currency":x["currency"],"base":float(x["base_pay"]),"hours":float(x["overtime_hours"]),"mult":float(x["overtime_multiplier"]),"allowance":0.0,"note":x["status"]})
    allowances=[]
    for i in range(1,5):
        code="HRD-"+"-".join("".join(rng.choice(string.ascii_uppercase+string.digits) for _ in range(4)) for _ in range(3))
        currency=("USD","EUR","GBP","USD")[i-1];amount=round(rng.uniform(190.00,1350.00),2);dept=("Engineering","Sales","Operations","People")[i-1]
        item={"id":f"ALW-{i:02d}","quarter":f"Q{i}","code":code,"currency":currency,"amount":amount,"department":dept}
        allowances.append(item);_memo_png(ga/f"in_b/allowances/{item['id']}.png",f"APPROVED ALLOWANCE {item['id']}",code,amount,currency,dept);item["sha256"]=hashlib.sha256((ga/f"in_b/allowances/{item['id']}.png").read_bytes()).hexdigest()
        hr_rows.append({"quarter":f"Q{i}","employee":item["id"],"department":dept,"currency":currency,"base":0.0,"hours":0.0,"mult":1.5,"allowance":amount,"note":"approved allowance"})
    truth={"fx":FX,"memos":memos,"allowances":allowances,"rev_rows":rev_rows,"hr_rows":hr_rows}
    rev_q={q:sum((r["gross"]-r["adj"])*FX[r["currency"]][0] for r in rev_rows if r["quarter"]==q) for q in ("Q1","Q2","Q3","Q4")}
    row_cost=lambda r:(r["base"]+r["base"]/173*r["hours"]*r["mult"]+r["allowance"])*FX[r["currency"]][0]*(1+FX[r["currency"]][1])
    hr_q={q:sum(row_cost(r) for r in hr_rows if r["quarter"]==q) for q in ("Q1","Q2","Q3","Q4")}
    truth["rev_quarter_usd"]={q:round(v,2) for q,v in rev_q.items()};truth["rev_adjustments_usd"]=round(sum(x["amount"]*FX[x["currency"]][0] for x in memos),2);truth["rev_total_usd"]=round(sum(rev_q.values()),2)
    truth["hr_quarter_usd"]={q:round(v,2) for q,v in hr_q.items()};truth["hr_allowances_usd"]=round(sum(x["amount"]*FX[x["currency"]][0]*(1+FX[x["currency"]][1]) for x in allowances),2);truth["hr_total_usd"]=round(sum(hr_q.values()),2)
    dept_totals={dept:round(sum(row_cost(r) for r in hr_rows if r["department"]==dept),2) for dept in ("Engineering","Sales","Operations","People")}
    truth["hr_department_usd"]=dept_totals;truth["hr_budgets"]={d:round(v*(0.76 if i<2 else 1.18),2) for i,(d,v) in enumerate(dept_totals.items())}
    for group,rows in (("rev_rows",rev_rows),("hr_rows",hr_rows)):
        # Store source-filled rows outside the answer key for build-time materialization only.
        pass
    _ledger_workbook(ga/"shared/Corp_Annual_2026.xlsx",truth)
    # Add readable, English work specifications.
    (ga/"in_a/close_spec_a.txt").write_text("Finance Close Workbook Guide\n\nUse the existing Rev_Ledger skeleton. Remove repeated invoice IDs but retain valid negative returns. Enter source lines and credit memos. Use live formulas that reference FX_Tax_Rates for currency conversions and quarter/year summaries. Do not flatten formulas or alter HR_Cost or FX_Tax_Rates. Export Rev_Ledger to PDF. Create a quarterly net revenue chart as rev_trend.png. Complete the open four-slide Finance_Close deck with the reconciled total, chart, risk notes, and an audit JSON.\n",encoding="utf-8")
    (ga/"in_b/close_spec_b.txt").write_text("People Close Workbook Guide\n\nUse the existing HR_Cost skeleton. Remove repeated time cards, retain valid correction entries, and calculate overtime as base pay divided by 173 hours, multiplied by overtime hours and the recorded multiplier. Enter the four approved allowance documents. Use live formulas that reference FX_Tax_Rates for currency conversion and employer tax, and for quarter/year summaries. Apply a conditional highlight to every over-budget department row using the department budget table beside the quarter summary in HR_Cost. Do not flatten formulas or alter Rev_Ledger or FX_Tax_Rates. Export HR_Cost to PDF. Create a quarterly people-cost chart as hr_cost_chart.png. Complete the open four-slide HR_Close deck with the reconciled total, chart, exception notes, and an audit JSON.\n",encoding="utf-8")
    _deck(ga/"out_a/Finance_Close.pptx","a");_deck(ga/"out_b/HR_Close.pptx","b")
    # Private answer key is staged only in the non-workspace case asset tree.
    private.mkdir(parents=True,exist_ok=True);(private/"expected.json").write_text(json.dumps(truth,indent=2),encoding="utf-8")
    return base


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("destination",type=Path);print(build(ap.parse_args().destination))
