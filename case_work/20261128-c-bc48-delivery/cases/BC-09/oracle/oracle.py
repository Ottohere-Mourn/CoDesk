"""Host-only deterministic grading for BC-09."""
from __future__ import annotations
import json, math, statistics, struct, zipfile, io, re
from xml.etree import ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from pipeline.grade import make_grade

REGIONS=("North","South","East","West")
FX=(1.0,1.08,1.27,.74)

def expected_finance():
    buckets={r:{"revenue_usd":0.0,"cost_usd":0.0} for r in REGIONS}
    for i in range(1,81):
        if i%11 in (0,1): continue
        region=REGIONS[(i-1)%4];rate=FX[(i-1)%4];amount=800+i*23.5;cost=amount*(.42+.01*(i%7))
        buckets[region]["revenue_usd"]+=amount*rate;buckets[region]["cost_usd"]+=cost*rate
    rows=[]
    for r in REGIONS:
        rev=buckets[r]["revenue_usd"];cost=buckets[r]["cost_usd"]
        rows.append({"region":r,"revenue_usd":round(rev,2),"cost_usd":round(cost,2),"gross_margin_pct":round((rev-cost)/rev*100,2)})
    revenue=sum(x["revenue_usd"] for x in rows);cost=sum(x["cost_usd"] for x in rows)
    return {"regions":rows,"total":{"revenue_usd":round(revenue,2),"cost_usd":round(cost,2),"gross_margin_pct":round((revenue-cost)/revenue*100,2)}}

def expected_product():
    accounts={f"AC-{u:03d}":(f"2026-{(u%3)+7:02d}",[(u+m)%5!=0 for m in range(4)], [180+((u*29+m*53)%420) for m in range(4)]) for u in range(1,61)}
    cohorts={}
    for uid,(cohort,active,lat) in accounts.items():cohorts.setdefault(cohort,[]).append((uid,active,lat))
    rows=[];num1=num3=0;den=0;latencies=[]
    for name,users in sorted(cohorts.items()):
        n=len(users);a1=sum(x[1][1] for x in users);a3=sum(x[1][3] for x in users);num1+=a1;num3+=a3;den+=n
        rows.append({"cohort_month":name,"cohort_size":n,"month1_retention_pct":round(a1/n*100,2),"month3_retention_pct":round(a3/n*100,2)})
        latencies.extend(x[2][m] for x in users for m in range(4))
    ordered=sorted(latencies);p95=ordered[math.ceil(.95*len(ordered))-1]
    median=statistics.median(ordered)
    return {"cohorts":rows,"overall":{"month1_retention_pct":round(num1/den*100,2),"month3_retention_pct":round(num3/den*100,2)},"latency_ms":{"median":round(median,1),"p95_nearest_rank":round(float(p95),1)},"unique_production_rows":240}

def _json(p):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return {}
def _png(p):
    try:
        b=p.read_bytes();return (struct.unpack(">II",b[16:24]) if b[:8]==b"\x89PNG\r\n\x1a\n" else (0,0))
    except (OSError,struct.error):return (0,0)
def _odp(path):
    try:
        with zipfile.ZipFile(path) as z:
            names=z.namelist();content=z.read("content.xml").decode("utf-8",errors="replace")
            return content,names
    except (OSError,zipfile.BadZipFile,KeyError):return "",[]
def _pdf(path):
    try:b=path.read_bytes();return b.startswith(b"%PDF-") and len(b)>500
    except OSError:return False

def _subset(actual, expected):
    if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and _subset(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(_subset(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,(int,float)):return isinstance(actual,(int,float)) and math.isclose(actual,expected,abs_tol=.011,rel_tol=0)
    return actual==expected

def _normalize_product(b):
    b=dict(b)
    def rates(row):
        return {f'month{n}_retention_pct':row.get(f'month{n}_retention_pct',row.get(f'month_{n}',{}).get('retention_pct')) for n in (1,3)}
    b['cohorts']=[dict(x,**rates(x)) for x in b.get('cohorts',[])]
    b['overall']=rates(b.get('overall',b.get('overall_account_weighted',{})))
    lat=b.get('latency_ms',b.get('production_latency_ms',{}))
    b['latency_ms']={'median':lat.get('median',lat.get('median_ms')),'p95_nearest_rank':lat.get('p95_nearest_rank',lat.get('p95_ms'))}
    b['unique_production_rows']=b.get('unique_production_rows',lat.get('n',b.get('cleaning',{}).get('clean_production_rows')))
    return b

def _slide_chart(path, section, finance):
    """Inspect the chart embedded in its actual slide, not unrequested PNG files."""
    ns={'draw':'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0','svg':'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0','xlink':'http://www.w3.org/1999/xlink','presentation':'urn:oasis:names:tc:opendocument:xmlns:presentation:1.0'}
    try:
        with zipfile.ZipFile(path) as z:
            if z.read('mimetype')!=b'application/vnd.oasis.opendocument.presentation':return False,False
            xml=ET.fromstring(z.read('content.xml'))
            page=next((x for x in xml.findall('.//draw:page',ns) if x.get('{'+ns['draw']+'}name')==section),None)
            if page is None:return False,False
            text=' '.join(page.itertext());notes=page.find('presentation:notes',ns)
            page_ok=bool(notes is not None and ''.join(notes.itertext()).strip() and len(text)>100)
            if section=='Finance':page_ok=page_ok and all(x in text for x in REGIONS) and 'margin' in text.lower()
            else:page_ok=page_ok and 'retention' in text.lower() and '95' in text
            image_ok=False
            for x in page.findall('.//draw:image',ns):
                name=x.get('{'+ns['xlink']+'}href','').removeprefix('./')
                if name not in z.namelist():continue
                from PIL import Image
                with Image.open(io.BytesIO(z.read(name))) as im:
                    w,h=im.size;im.verify();image_ok=image_ok or (w>=320 and h>=180)
            vector_ok=False
            if section=='Finance':
                def dim(x,key):
                    v=x.get('{'+ns['svg']+'}'+key,'0');m=re.fullmatch(r'([0-9.]+)(cm|mm|in|pt)',v)
                    return float(m[1])*{'cm':1,'mm':.1,'in':2.54,'pt':2.54/72}[m[2]] if m else 0
                bars=[x for x in page.findall('.//draw:rect',ns) if .1<=dim(x,'height')<=1.5 and dim(x,'width')>dim(x,'height')]
                values=sorted(x['revenue_usd'] for x in finance['regions'])
                for include_total in (False,True):
                    target=sorted(values+([finance['total']['revenue_usd']] if include_total else []))
                    if len(bars)!=len(target):continue
                    widths=sorted(dim(x,'width') for x in bars)
                    vector_ok=all(abs(w/max(widths)-v/max(target))<=.015 for w,v in zip(widths,target))
                    if vector_ok:break
            return bool(image_ok or vector_ok),bool(page_ok and (image_ok or vector_ok))
    except (OSError,KeyError,ValueError,zipfile.BadZipFile,ET.ParseError):return False,False

def grade_episode(snapshot_root:Path,receipt:dict[str,Any],run_id:str):
    out=Path(snapshot_root).parent/"guest-output";a=_json(out/"finance_summary.json");b=_json(out/"product_summary.json")
    finance=expected_finance();product=expected_product();raw_b=b;b=_normalize_product(b);a_chart=_png(out/"finance_chart.png");b_chart=_png(out/"product_chart.png");content,names=_odp(out/"q4_board_deck.odp")
    a_values=_subset(a.get('regional_summary',a.get('regions')),finance['regions']) and _subset(a.get('total'),finance['total'])
    # Rules did not prescribe a percentile convention. Accept nearest-rank or
    # the explicitly reported linear convention, independently recomputed here.
    method=str(raw_b.get('production_latency_ms',{}).get('percentile_method','')).lower()
    if 'linear' in method:
        ordered=sorted(180+((u*29+m*53)%420) for u in range(1,61) for m in range(4))
        rank=Decimal('0.95')*(len(ordered)-1);lo=int(rank);hi=math.ceil(rank)
        interpolated=Decimal(ordered[lo])+Decimal(ordered[hi]-ordered[lo])*(rank-lo)
        product['latency_ms']['p95_nearest_rank']=float(interpolated.quantize(Decimal('0.1'),rounding=ROUND_HALF_UP))
    b_values=_subset(b.get('cohorts'),product['cohorts']) and _subset(b.get('overall'),product['overall']) and _subset(b.get('latency_ms'),product['latency_ms']) and b.get('unique_production_rows')==product['unique_production_rows']
    picture_count=sum(1 for name in names if name.startswith("Pictures/") and not name.endswith("/"))
    a_png,a_page=_slide_chart(out/'q4_board_deck.odp','Finance',finance)
    b_png,b_page=_slide_chart(out/'q4_board_deck.odp','Product',finance)
    finance_pdf=_pdf(out/"finance_summary.pdf");product_pdf=_pdf(out/"product_summary.pdf")
    checks_a=[("A01",.30,a_values,{"expected":finance,"observed":a.get("regional_summary",a.get("regions"))}),("A02",.20,a_png,{"embedded_chart_valid":a_png,"external_png_required":False}),("A03",.20,finance_pdf,{"pdf_valid":finance_pdf}),("A04",.20,a_page,{"finance_content_and_chart_embedded":a_page}),("A05",.10,"gross_margin_pct" in json.dumps(a),{"has_margin_metric":"gross_margin_pct" in json.dumps(a)})]
    checks_b=[("B01",.30,b_values,{"expected":product,"observed":{k:b.get(k) for k in ("cohorts","overall","latency_ms","unique_production_rows")}}),("B02",.20,b_png,{"embedded_chart_valid":b_png,"external_png_required":False}),("B03",.20,product_pdf,{"pdf_valid":product_pdf}),("B04",.20,b_page,{"product_content_and_chart_embedded":b_page}),("B05",.10,"month3_retention_pct" in json.dumps(b),{"has_month3_retention": "month3_retention_pct" in json.dumps(b)})]
    def c(cid,w,ok,e):return {"id":cid,"weight":w,"passed":bool(ok),"score":float(bool(ok)),"required":True,"evidence":e}
    deck=out/"q4_board_deck.odp";valid_odp=bool(content and len(names)>=4 and deck.is_file())
    joint=[c("J01",1,valid_odp,{"valid_odp_package":valid_odp}),c("J02",1,a_page and b_page,{"finance_and_product_sections_retained":a_page and b_page}),c("J03",1,a_png and b_png,{"both_chart_assets_valid":a_png and b_png,"embedded_picture_count":picture_count})]
    return make_grade(case_id="BC-09",run_id=run_id,actor_a_checks=[c(*x) for x in checks_a],actor_b_checks=[c(*x) for x in checks_b],joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,failure_reasons=[] if (Path(snapshot_root)/"transactions.db").is_file() else ["Host-side transaction DB snapshot is missing."],run_metadata={"oracle":"BC-09 deterministic fixed-fixture aggregation"})
