"""Private, deterministic 46-check evaluator for CONC-08."""
from __future__ import annotations
import hashlib,json,math,re,shutil,subprocess,tempfile
from pathlib import Path

ERRORS=("#REF!","#VALUE!","#NAME?","#DIV/0!","#N/A","#NUM!")

def _load_json(p):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError,TypeError):return {}

def _excel(out,render):
    src=Path(out)/"Corp_Annual_2026.xlsx";rd=Path(render)/"recalc";rd.mkdir(parents=True,exist_ok=True)
    bin=shutil.which("libreoffice") or shutil.which("soffice")
    if not src.is_file() or not bin:return None
    profile=Path(render)/"lo-profile";profile.mkdir(parents=True,exist_ok=True)
    try:
        p=subprocess.run([bin,f"-env:UserInstallation=file://{profile.as_posix()}","--headless","--convert-to","xlsx","--outdir",str(rd),str(src)],capture_output=True,text=True,timeout=150)
        got=rd/src.name
        if p.returncode==0 and got.is_file():return got
    except (OSError,subprocess.TimeoutExpired):pass
    return None

def _close(a,b,tol=0.01):
    try:return abs(float(a)-float(b))<tol
    except (TypeError,ValueError):return False

def _workbook(out,expected,render):
    p=Path(out)/"Corp_Annual_2026.xlsx"
    if not p.is_file():return None,None,None
    try:
        from openpyxl import load_workbook
        wf=load_workbook(p,data_only=False);cached_path=_excel(out,render);wv=load_workbook(cached_path or p,data_only=True)
        return wf,wv,cached_path
    except Exception:return None,None,None

def _pdf(pdf_path,render,expected_pages=None,require_text=True):
    try:import fitz
    except Exception:return False,0
    p=Path(pdf_path)
    if not p.is_file():return False,0
    try:
        doc=fitz.open(p);ok=len(doc)>0 and (expected_pages is None or len(doc)==expected_pages);render=Path(render);render.mkdir(parents=True,exist_ok=True);nonblank=0
        for i,page in enumerate(doc):
            pix=page.get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False);dest=render/f"{p.stem}-page-{i+1:02d}.png";pix.save(dest)
            text=page.get_text().strip();samples=pix.samples;colored=sum(1 for x in samples[::3] if x<242)
            if colored>250 or (not require_text and bool(text)):nonblank+=1
            if require_text and len(text)<12:ok=False
        return bool(ok and nonblank==len(doc)),len(doc)
    except Exception:return False,0

def _records(state,actor):
    return sorted((state.get("records",{}).get(actor) or []),key=lambda x:x.get("id",0))

def _output_json(out,filename):return _load_json(Path(out)/filename)

def _token_artifacts(ws,actor,exp,state=None):
    st=state if isinstance(state,dict) else _load_json(Path(ws)/"state.json");records=_records(st,actor);rows=exp["memos"] if actor=="a" else exp["allowances"]
    checks=[];contaminators=[]
    for i,row in enumerate(rows,1):
        got=next((r for r in records if r.get("id")==i),{})
        checks.append(bool(got and got.get("code")==row["code"] and _close(got.get("amount"),row["amount"])))
        checks.append(bool(got and got.get("category")==row["category" if actor=="a" else "department"]))
        checks.append(bool(got and got.get("file_sha256")==row["sha256"]))
        wrong="HRD-" if actor=="a" else "FIN-"
        contaminators.append(any(wrong in str(r.get("code","")) for r in records))
    return st,records,checks,not any(contaminators)

def _ppt(path):
    try:
        from pptx import Presentation
        prs=Presentation(path);texts=[sh.text for slide in prs.slides for sh in slide.shapes if getattr(sh,"has_text_frame",False)]
        return prs,texts
    except Exception:return None,[]

def _num_in_text(text,value):
    for token in re.findall(r"(?<!\w)\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?!\w)|(?<!\w)\d+\.\d{2}(?!\w)",str(text)):
        try:
            if _close(float(token.replace(",","")),value,0.01):return True
        except ValueError:pass
    return False

def _chart(path,pres,actor):
    try:
        p=Path(path);target=hashlib.sha256(p.read_bytes()).hexdigest();slide=pres.slides[2];pics=[];text_shapes=[]
        for sh in slide.shapes:
            if sh.shape_type==13:pics.append((sh,hashlib.sha256(sh.image.blob).hexdigest()))
            elif getattr(sh,"has_text_frame",False) and sh.text.strip():text_shapes.append(sh)
        match=[x for x in pics if x[1]==target]
        if not match:return False
        pic=match[0][0];pr,pt,ph,pw=pic.left,pic.top,pic.height,pic.width
        for sh in text_shapes:
            if max(pr,sh.left)<min(pr+pw,sh.left+sh.width) and max(pt,sh.top)<min(pt+ph,sh.top+sh.height):return False
        return True
    except Exception:return False

def _fx_untampered(wb,expected):
    try:
        sh=wb["FX_Tax_Rates"]
        for i,cur in enumerate(("USD","EUR","GBP"),2):
            rate,tax=expected["fx"][cur]
            if sh.cell(i,1).value!=cur or not _close(sh.cell(i,2).value,rate,1e-6) or not _close(sh.cell(i,3).value,tax,1e-6):return False
        return True
    except Exception:return False

def _formula_ok(wb,actor):
    try:
        sh=wb["Rev_Ledger"] if actor=="a" else wb["HR_Cost"]
        n=38
        if actor=="a":
            fx=all(isinstance(sh.cell(r,6).value,str) and "FX_Tax_Rates!" in sh.cell(r,6).value for r in range(2,n))
            sums=all(isinstance(sh.cell(r,11).value,str) and "=" in sh.cell(r,11).value for r in range(2,6)) and "=" in str(sh["K7"].value) and "=" in str(sh["K8"].value)
            gross=all(isinstance(sh.cell(r,7).value,str) and "=" in sh.cell(r,7).value for r in range(2,n))
        else:
            fx=all(isinstance(sh.cell(r,9).value,str) and "FX_Tax_Rates!" in sh.cell(r,9).value and "FX_Tax_Rates!" in str(sh.cell(r,10).value) for r in range(2,n))
            sums=all(isinstance(sh.cell(r,15).value,str) and "=" in sh.cell(r,15).value for r in range(2,6)) and "=" in str(sh["O7"].value) and "=" in str(sh["O8"].value)
            gross=all(isinstance(sh.cell(r,11).value,str) and "=" in sh.cell(r,11).value for r in range(2,n))
        return bool(fx and sums and gross)
    except Exception:return False

def _no_errors(wb):
    try:
        for sh in wb.worksheets:
            for row in sh.iter_rows():
                for c in row:
                    if c.data_type=="e" or (isinstance(c.value,str) and c.value.startswith(ERRORS)):return False
        return True
    except Exception:return False

def _formula_totals(wv,actor,exp):
    try:
        sh=wv["Rev_Ledger"] if actor=="a" else wv["HR_Cost"]
        qs=exp["rev_quarter_usd"] if actor=="a" else exp["hr_quarter_usd"]
        col=11 if actor=="a" else 15
        quarter=[_close(sh.cell(r,col).value,qs[f"Q{r-1}"]) for r in range(2,6)]
        adj=_close(sh["K7" if actor=="a" else "O7"].value,exp["rev_adjustments_usd"] if actor=="a" else exp["hr_allowances_usd"])
        total=_close(sh["K8" if actor=="a" else "O8"].value,exp["rev_total_usd"] if actor=="a" else exp["hr_total_usd"])
        return quarter,adj,total
    except Exception:return [False]*4,False,False

def _json_ok(doc,actor,exp,state):
    if not doc:return False
    prefix="rev" if actor=="a" else "hr"
    qkey="quarterly_usd";tkey="annual_total_usd";akey="memo_adjustments_usd" if actor=="a" else "allowance_cost_usd"
    quarters=exp["rev_quarter_usd"] if actor=="a" else exp["hr_quarter_usd"];total=exp["rev_total_usd"] if actor=="a" else exp["hr_total_usd"];adj=exp["rev_adjustments_usd"] if actor=="a" else exp["hr_allowances_usd"]
    try:
        exact=all(_close(doc[qkey][q],v) for q,v in quarters.items()) and _close(doc[tkey],total) and _close(doc[akey],adj)
        close=doc.get("close_code")==state.get("finalized",{}).get(actor)
        source=doc.get("source_records",[]);expected=exp["memos"] if actor=="a" else exp["allowances"]
        details=len(source)==4 and all(any(x.get("id")==e["id"] and x.get("verification_code")==e["code"] and _close(x.get("amount"),e["amount"]) and x.get("category" if actor=="a" else "department")==e["category" if actor=="a" else "department"] for x in source) for e in expected)
        return bool(exact and close and details)
    except (KeyError,TypeError):return False

def _actor(ws,state,expected_path,render,actor):
    exp=_load_json(expected_path);checks={};out=Path(ws);actor_dir="out_a" if actor=="a" else "out_b";xlsx=out/"Corp_Annual_2026.xlsx"
    wf,wv,recalc=_workbook(out,exp,render);st,records,sitechecks,nocross=_token_artifacts(ws,actor,exp,state)
    if wf is None or wv is None:
        # Still populate every checkpoint so infra failures are explicit and machine-readable.
        for i in range(1,24):checks[f"{actor.upper()}{i:02d}"]=False
        return checks
    sheets=set(wf.sheetnames);checks[f"{actor.upper()}01"]={"Rev_Ledger","HR_Cost","FX_Tax_Rates"}.issubset(sheets)
    checks[f"{actor.upper()}02"]=_formula_ok(wf,actor)
    checks[f"{actor.upper()}03"]=_no_errors(wv)
    quarters,adj_ok,total_ok=_formula_totals(wv,actor,exp)
    for i,ok in enumerate(quarters,4):checks[f"{actor.upper()}{i:02d}"]=ok
    checks[f"{actor.upper()}08"]=adj_ok;checks[f"{actor.upper()}09"]=total_ok
    pdf1="Rev_Ledger.pdf" if actor=="a" else "HR_Cost.pdf";p1ok,_=_pdf(out/pdf1,Path(render)/actor/f"{pdf1}-pages",None,True);checks[f"{actor.upper()}10"]=p1ok
    for i in range(4):checks[f"{actor.upper()}{11+i:02d}"]=sitechecks[i*3] and sitechecks[i*3+1]
    checks[f"{actor.upper()}15"]=all(sitechecks[i*3+2] for i in range(4))
    wrong="HRD-" if actor=="a" else "FIN-";sheet=wf["Rev_Ledger"] if actor=="a" else wf["HR_Cost"]
    json_name="finance_close.json" if actor=="a" else "hr_close.json";jdoc=_output_json(out,json_name)
    sheettext=" ".join(str(c.value) for row in sheet.iter_rows() for c in row if c.value is not None)
    checks[f"{actor.upper()}16"]=bool(nocross and wrong not in sheettext and wrong not in json.dumps(jdoc,ensure_ascii=False))
    deck="Finance_Close.pptx" if actor=="a" else "HR_Close.pptx";prs,texts=_ppt(out/deck);checks[f"{actor.upper()}17"]=bool(prs and len(prs.slides)==4)
    total=exp["rev_total_usd"] if actor=="a" else exp["hr_total_usd"];fulltext=" ".join(texts)
    checks[f"{actor.upper()}18"]=_num_in_text(fulltext,total)
    chart="rev_trend.png" if actor=="a" else "hr_cost_chart.png";checks[f"{actor.upper()}19"]=bool(prs and (out/chart).is_file() and _chart(out/chart,prs,actor))
    lastslide=prs.slides[3] if prs and len(prs.slides)>3 else None;lasttext=" ".join(sh.text for sh in lastslide.shapes if getattr(sh,"has_text_frame",False)) if lastslide else ""
    needed=("risk","source","reviewer") if actor=="a" else ("exception","source","reviewer")
    fits=bool(lastslide and all(w in lasttext.lower() for w in needed) and all(sh.top+sh.height<=prs.slide_height for sh in lastslide.shapes))
    checks[f"{actor.upper()}20"]=fits
    pdf2="Finance_Close.pdf" if actor=="a" else "HR_Close.pdf";p2ok,pages=_pdf(out/pdf2,Path(render)/actor/f"{pdf2}-pages",4,True);checks[f"{actor.upper()}21"]=bool(p2ok and pages==4)
    checks[f"{actor.upper()}22"]=_json_ok(jdoc,actor,exp,st)
    checks[f"{actor.upper()}23"]=_fx_untampered(wf,exp) and ("HR_Cost" in wf.sheetnames if actor=="a" else "Rev_Ledger" in wf.sheetnames)
    if actor=="b":
        # Verify the required sheet-level conditional formatting still covers every ledger row.
        try:
            cf=wf["HR_Cost"].conditional_formatting
            rules=[r for _,rr in cf._cf_rules.items() for r in rr]
            budget=wf["HR_Cost"]
            budget_ok=all(budget.cell(i,17).value==d and _close(budget.cell(i,18).value,exp["hr_budgets"][d]) for i,d in enumerate(("Engineering","Sales","Operations","People"),2))
            checks["B09"]=checks["B09"] and budget_ok and any("SUMIF" in " ".join(r.formula or []) and "$Q$2:$R$5" in " ".join(r.formula or []) for r in rules)
        except Exception:checks["B09"]=False
    return checks

def grade(workspace,state,expected_path,render_dir):
    a=_actor(workspace,state,expected_path,Path(render_dir)/"actor-a","a");b=_actor(workspace,state,expected_path,Path(render_dir)/"actor-b","b")
    source_state=state if isinstance(state,dict) else _load_json(Path(workspace)/"state.json")
    flags={"formula_recalc_available":bool(shutil.which("libreoffice") or shutil.which("soffice")),"shared_records":len(_records(source_state,"a"))+len(_records(source_state,"b")),"concurrency_metrics":source_state.get("metrics",{})}
    return {"actor_a":sum(bool(v) for v in a.values()),"actor_b":sum(bool(v) for v in b.values()),"checks":{"actor_a":a,"actor_b":b},"flags":flags}
