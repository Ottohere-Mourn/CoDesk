"""Private deterministic 44-check oracle for CONC-07."""
from __future__ import annotations
import hashlib,json,os,sqlite3
from pathlib import Path
def _read(p):
    try:return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError,UnicodeError,json.JSONDecodeError):return None
def _sha(p):
    try:return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except OSError:return ''
def _expected(p=None):
    q=Path(p) if p else Path(os.environ.get('PARAGUI_TASK_ASSETS',''))/'CONC-07/private/expected.json'
    try:return json.loads(q.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return {}
def _n(x):
    try:return float(str(x).replace('$','').replace(',','').replace('x','').replace('X','').strip())
    except (ValueError,TypeError):return None
def _db(path):
    try:
        c=sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True);c.row_factory=sqlite3.Row
        check=c.execute('PRAGMA integrity_check').fetchone()[0]
        a=[dict(x) for x in c.execute('SELECT * FROM supplier_settlements ORDER BY supplier_id')]
        b=[dict(x) for x in c.execute('SELECT * FROM campaign_audits ORDER BY channel_id')];c.close();return check,a,b
    except sqlite3.Error:return '',[],[]
def _slides(path):
    try:
        from pptx import Presentation
        return Presentation(str(path))
    except Exception:return None
def _pics(slide):return [s for s in slide.shapes if getattr(s,'shape_type',None)==13]
def _slide_text(slide):return '\n'.join(s.text_frame.text for s in slide.shapes if getattr(s,'has_text_frame',False))
def _color(prs,want):
    try:
        rgb=bytes.fromhex(want.lstrip('#'))
        for s in prs.slides[0].shapes:
            try:
                if s.fill.type is not None and bytes(s.fill.fore_color.rgb)==rgb:return True
            except Exception:continue
        return False
    except Exception:return False
def _safe_images(prs,slides):
    try:
        for idx in slides:
            slide=prs.slides[idx];imgs=_pics(slide);texts=[s for s in slide.shapes if getattr(s,'has_text_frame',False) and s.text_frame.text.strip()]
            for im in imgs:
                if im.left<0 or im.top<0 or im.left+im.width>prs.slide_width or im.top+im.height>prs.slide_height:return False
                for tx in texts:
                    if max(0,min(im.left+im.width,tx.left+tx.width)-max(im.left,tx.left))*max(0,min(im.top+im.height,tx.top+tx.height)-max(im.top,tx.top))>0:return False
        return True
    except Exception:return False
def _pdf_check(path,render_dir,expected_colors,required_text):
    try:
        import fitz
        from PIL import Image
        doc=fitz.open(path)
    except Exception:return False
    if len(doc)!=7:doc.close();return False
    out=Path(render_dir);out.mkdir(parents=True,exist_ok=True);ok=True
    for i,page in enumerate(doc):
        p=out/f'page-{i+1}.png';page.get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(p)
        try:
            im=Image.open(p).convert('RGB');pixels=list(im.getdata());nonwhite=sum(1 for x in pixels if min(x)<240)
            target=tuple(bytes.fromhex(expected_colors[i].lstrip('#'))) if i<len(expected_colors) and expected_colors[i] else None
            colored=sum(1 for x in pixels if target and sum(abs(x[k]-target[k]) for k in range(3))<8)
            ok &= nonwhite>800 and (i==0 or target is None or colored>100)
        except Exception:ok=False
    text=' '.join('\n'.join(x.get_text() for x in doc).lower().split());ok &= all(' '.join(x.lower().split()) in text for x in required_text);doc.close();return bool(ok)
def _a(ws,state,exp,render):
    rows=exp.get('suppliers',[]);dbfile=Path(ws)/'enterprise_ops.db';integrity,arows,_=_db(dbfile);by={x.get('supplier_id'):x for x in arows};checks=[]
    checks.append(integrity=='ok' and len(arows)==6)
    for x in rows:
        q=by.get(x['supplier_id'],{});checks.append(all(q.get(k) is not None and abs(float(q[k])-float(x[k]))<1e-2 for k in ('gross_amount','deduction','net_payable','has_dispute')))
    events=state.get('a_events',[]);uploaded={}
    for e in events:
        if e.get('type')=='row_saved' and e.get('image_sha256'):uploaded[e.get('id')]=e.get('image_sha256')
    checks.append(all(uploaded.get(sid)==exp.get('supplier_qc_hashes',{}).get(sid) for sid in ('SUP-02','SUP-05')))
    fin=next((e for e in state.get('finalize_events',[]) if e.get('type')=='finalize_success'),{});code=fin.get('code');checks.append(bool(code and len(arows)==6 and all(x.get('batch_code')==code for x in arows)))
    out=Path(ws)/'out_a';audit=_read(out/'settlement_audit.json');checks.append(isinstance(audit,dict) and audit.get('batch_code')==code and audit.get('settlements')==rows and audit.get('exceptions')==exp.get('supplier_exceptions'))
    prs=_slides(out/'Q4_Supplier_Review.pptx');checks.append(prs is not None and len(prs.slides)==7)
    checks.append(prs is not None and _color(prs,exp.get('brand_a','#2E7D32')))
    if prs is not None:
        try:
            table=next(s.table for s in prs.slides[1].shapes if s.has_table);rowchecks=[]
            for i,x in enumerate(rows,1):
                row=table.rows[i].cells;rowchecks.append(row[0].text.strip()==x['supplier_id'] and [_n(row[j].text) for j in (1,2,3)]==[float(x[k]) for k in ('gross_amount','deduction','net_payable')])
            checks.append(all(rowchecks[:3]));checks.append(all(rowchecks[3:]))
        except Exception:checks.extend([False,False])
        charts=list(exp.get('supplier_chart_hashes',{}).items());
        for i,(name,want) in enumerate(charts[:3],2):
            try:checks.append(any(_sha_bytes(s.image.blob)==want for s in _pics(prs.slides[i])))
            except Exception:checks.append(False)
        checks.append(_safe_images(prs,[2,3,4]))
        exception_text=_slide_text(prs.slides[5]).lower();checks.append(all(s.lower() in exception_text for s in exp.get('supplier_exceptions',{})) and all(v.lower() in exception_text for v in exp.get('supplier_exceptions',{}).values()))
        note=_slide_text(prs.slides[6]);checks.append(exp.get('a_note','') in note and all(s.top+s.height<=prs.slide_height for s in prs.slides[6].shapes if getattr(s,'has_text_frame',False) and s.text_frame.text.strip()))
    else:checks.extend([False]*7)
    pdf=out/'Q4_Supplier_Review.pdf';checks.append(_pdf_pages(pdf)==7)
    checks.append(_pdf_check(pdf,Path(render)/'a', [exp.get('brand_a'),None,exp.get('brand_a'),exp.get('brand_a'),exp.get('brand_a'),None,exp.get('brand_a')],[exp.get('a_note','')]))
    return checks
def _sha_bytes(b):return hashlib.sha256(b).hexdigest()
def _pdf_pages(p):
    try:
        import fitz
        with fitz.open(p) as d:return len(d)
    except Exception:return 0
def _b(ws,state,exp,render):
    rows=exp.get('campaigns',[]);integrity,_,brows=_db(Path(ws)/'enterprise_ops.db');by={x.get('channel_id'):x for x in brows};checks=[]
    checks.append(integrity=='ok' and len(brows)==6)
    for x in rows:
        q=by.get(x['channel_id'],{});checks.append(all(q.get(k) is not None and abs(float(q[k])-float(x[k]))<1e-2 for k in ('spend','revenue','roi','alert_flag')))
    ev=state.get('b_events',[]);mob=[e for e in ev if e.get('type')=='mobile_viewport_check' and 355<=int(e.get('width',0))<=395];wide=[e for e in ev if e.get('type')=='dashboard_hover' and int(e.get('width',0))>=1600 and e.get('channel') in exp.get('campaign_ids',[])];checks.append(len(mob)>=2 and {e.get('channel') for e in wide}==set(exp.get('campaign_ids',[])))
    try:
        from PIL import Image
        mb=state.get('mobile_uploads',[]);valid=True
        for i in (1,2):
            p=Path(ws)/'out_b'/f'mobile_lp_{i}.png';im=Image.open(p);valid &= im.size==(375,812) and _sha(p)==exp.get('mobile_hashes',{}).get(f'LP-{i}') and any(x.get('name')==p.name and x.get('sha256')==_sha(p) for x in mb)
        checks.append(bool(valid))
    except Exception:checks.append(False)
    lock=next((x for x in state.get('finalize_events',[]) if x.get('type')=='lock_success'),{});code=lock.get('code');checks.append(bool(code and len(brows)==6 and all(x.get('lock_code')==code for x in brows)))
    out=Path(ws)/'out_b';summary=_read(out/'campaign_summary.json');checks.append(isinstance(summary,dict) and summary.get('lock_code')==code and summary.get('campaigns')==rows and summary.get('allowances')==exp.get('allowances'))
    prs=_slides(out/'Promo_Postmortem.pptx');checks.append(prs is not None and len(prs.slides)==7 and 'budget' in _slide_text(prs.slides[2]).lower() and 'budget' in _slide_text(prs.slides[3]).lower())
    checks.append(prs is not None and _color(prs,exp.get('brand_b','#1565C0')))
    if prs is not None:
        try:
            table=next(s.table for s in prs.slides[1].shapes if s.has_table);good=[]
            for i,x in enumerate(rows,1):
                r=table.rows[i].cells;good.append(r[0].text.strip()==x['channel_id'] and all(_n(r[j].text) is not None and abs(_n(r[j].text)-float(x[k]))<1e-2 for j,k in ((1,'spend'),(2,'revenue'),(3,'roi'))) and r[4].text.strip().lower() in ({'review','yes','alert'} if x['alert_flag'] else {'within plan','no','clear'}))
            checks.append(all(good[:3]));checks.append(all(good[3:]))
        except Exception:checks.extend([False,False])
        specs=[('channel_roi',2),('budget_variance',2),('revenue_mix',3)]
        for name,idx in specs:
            want=exp.get('campaign_chart_hashes',{}).get(name);items=_pics(prs.slides[idx]);used=len([z for z in items if _sha_bytes(z.image.blob) in exp.get('campaign_chart_hashes',{}).values()]);checks.append(any(_sha_bytes(s.image.blob)==want for s in items) and (idx!=2 or used>=2))
        checks.append(_safe_images(prs,[2,3,4]))
        note=_slide_text(prs.slides[6]);checks.append(exp.get('b_note','') in note and all(s.top+s.height<=prs.slide_height for s in prs.slides[6].shapes if getattr(s,'has_text_frame',False) and s.text_frame.text.strip()))
    else:checks.extend([False]*7)
    pdf=out/'Promo_Postmortem.pdf';checks.append(_pdf_pages(pdf)==7)
    checks.append(_pdf_check(pdf,Path(render)/'b',[exp.get('brand_b'),None,exp.get('brand_b'),exp.get('brand_b'),exp.get('brand_b'),None,exp.get('brand_b')],[exp.get('b_note','')]))
    return checks
def grade(workspace,state=None,expected_path=None,render_dir=None):
    ws=Path(workspace);exp=_expected(expected_path);state=state or {};render=Path(render_dir or ws/'rendered');a=_a(ws,state,exp,render);b=_b(ws,state,exp,render)
    return {'actor_a':sum(a)/22,'actor_b':sum(b)/22,'joint_pass':all(a) and all(b),'checks':{'actor_a':a,'actor_b':b},'flags':[*(f'A{i+1}' for i,x in enumerate(a) if not x),*(f'B{i+1}' for i,x in enumerate(b) if not x)]}
