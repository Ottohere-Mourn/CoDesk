"""Create English-only supplier packets, campaign data and seven-slide drafts."""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pptx import Presentation
from pptx.util import Inches,Pt

SUPPLIERS=[
 {"supplier_id":"SUP-01","gross_amount":18450.75,"deduction":0.0,"net_payable":18450.75,"has_dispute":0,"reason":"No deduction; invoice matched purchase order."},
 {"supplier_id":"SUP-02","gross_amount":27900.0,"deduction":1250.0,"net_payable":26650.0,"has_dispute":1,"reason":"Deduct 1,250.00 for a duplicate freight line."},
 {"supplier_id":"SUP-03","gross_amount":12340.5,"deduction":0.0,"net_payable":12340.5,"has_dispute":0,"reason":"No deduction; received quantity confirmed."},
 {"supplier_id":"SUP-04","gross_amount":38999.0,"deduction":0.0,"net_payable":38999.0,"has_dispute":0,"reason":"No deduction; quality certificate is complete."},
 {"supplier_id":"SUP-05","gross_amount":21875.25,"deduction":750.0,"net_payable":21125.25,"has_dispute":1,"reason":"Deduct 750.00 for two cartons damaged in transit."},
 {"supplier_id":"SUP-06","gross_amount":45200.5,"deduction":0.0,"net_payable":45200.5,"has_dispute":0,"reason":"No deduction; service milestone accepted."},
]
CAMPAIGNS=[
 {"channel_id":"CH-01","spend":12000.0,"revenue":34800.0,"roi":1.9,"alert_flag":0,"budget":15000.0},
 {"channel_id":"CH-02","spend":18500.0,"revenue":59200.0,"roi":2.2,"alert_flag":1,"budget":17000.0},
 {"channel_id":"CH-03","spend":9800.0,"revenue":27440.0,"roi":1.8,"alert_flag":0,"budget":11000.0},
 {"channel_id":"CH-04","spend":22400.0,"revenue":64960.0,"roi":1.9,"alert_flag":1,"budget":21000.0},
 {"channel_id":"CH-05","spend":15750.0,"revenue":50400.0,"roi":2.2,"alert_flag":0,"budget":16000.0},
 {"channel_id":"CH-06","spend":8100.0,"revenue":17820.0,"roi":1.2,"alert_flag":0,"budget":9000.0},
]
ALLOWANCES=[{"id":"ALW-01","token":"HRD-0184-2751-6309","amount":142.50},{"id":"ALW-02","token":"HRD-5720-1186-4403","amount":86.25},{"id":"ALW-03","token":"HRD-3907-5521-8046","amount":315.00},{"id":"ALW-04","token":"HRD-6642-9017-3358","amount":74.80}]
SUP_CHARTS=["settlement_by_vendor","deduction_profile","q4_payable_trend"]
CAM_CHARTS=["channel_roi","budget_variance","revenue_mix"]
SUP_COLOR="#2E7D32";CAM_COLOR="#1565C0"
def font(size,bold=False):
    for n in (("DejaVuSans-Bold.ttf","arialbd.ttf") if bold else ("DejaVuSans.ttf","arial.ttf")):
        try:return ImageFont.truetype(n,size)
        except OSError:pass
    return ImageFont.load_default()
def card(path,title,lines,color="#2E7D32"):
    im=Image.new("RGB",(1100,760),"#f5f7fa");d=ImageDraw.Draw(im);d.rounded_rectangle((24,24,1076,736),radius=26,fill="white",outline="#cbd5e1",width=3);d.rectangle((24,24,1076,150),fill=color);d.text((58,65),title,font=font(34,True),fill="white");y=195
    for label,value in lines:
        d.text((70,y),label.upper(),font=font(18,True),fill="#526579");d.rounded_rectangle((68,y+34,1030,y+94),radius=8,fill="#f1f5f9",outline="#d8e1ea",width=2);d.text((90,y+49),str(value),font=font(25,True),fill="#172f45");y+=125
    im.save(path,format="PNG",optimize=True)
def chart(path,title,labels,values,color):
    im=Image.new("RGB",(1280,800),"#f6f8fb");d=ImageDraw.Draw(im);d.text((45,34),title,font=font(30,True),fill="#1d3550");negative=min(values)<0;baseline=420 if negative else 680;scale=230 if negative else 470;d.line((95,baseline,1190,baseline),fill="#63768a",width=3);maxv=max(abs(v) for v in values)*1.15
    for i,(lab,val) in enumerate(zip(labels,values)):
        x=125+i*170;h=max(1,int(scale*abs(val)/maxv));y0,y1=(baseline-h,baseline) if val>=0 else (baseline,baseline+h);d.rounded_rectangle((x,y0,x+92,y1),radius=10,fill=color);d.text((x,y0-34 if val>=0 else y1+5),f"{val:,.0f}",font=font(16,True),fill="#334155");d.text((x+10,710),lab,font=font(16,True),fill="#475569")
    im.save(path,format="PNG",optimize=True)
def swatch(path,color):
    im=Image.new("RGB",(640,390),"white");d=ImageDraw.Draw(im);d.rounded_rectangle((20,20,620,370),radius=18,fill=color);d.text((70,285),"APPROVED BRAND COLOR",font=font(25,True),fill="white");im.save(path,format="PNG")
def mobile(path,title,body,color):
    im=Image.new("RGB",(375,812),"#f5f7fa");d=ImageDraw.Draw(im);d.rectangle((0,0,375,78),fill=color);d.text((20,26),"ADPULSE 2026",font=font(20,True),fill="white");d.rounded_rectangle((18,110,357,430),radius=18,fill="white",outline="#d5dfe8",width=2);d.text((38,145),title,font=font(21,True),fill="#18344d");
    for i,line in enumerate(body):d.text((38,205+i*36),line,font=font(15),fill="#485b6d")
    d.rounded_rectangle((38,350,330,395),radius=10,fill=color);d.text((112,363),"Explore offer",font=font(15,True),fill="white");d.rounded_rectangle((18,465,357,755),radius=18,fill="white",outline="#d5dfe8",width=2);d.text((38,495),"Details and next steps",font=font(18,True),fill="#18344d");d.text((38,548),"Clear, accessible, and responsive",font=font(14),fill="#485b6d");im.save(path,format="PNG")
def deck(path,title,actor):
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    def text(s,x,y,w,h,t,size=20,bold=False):
        sh=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));sh.text_frame.word_wrap=True;sh.text_frame.text=t
        for p in sh.text_frame.paragraphs:
            for r in p.runs:r.font.size=Pt(size);r.font.bold=bold
        return sh
    def slide(t,body):
        s=prs.slides.add_slide(prs.slide_layouts[6]);text(s,.65,.35,12,.55,t,26,True);text(s,.65,1.0,5.1,4.7,body,16);text(s,6.1,1.65,6.35,3.9,"Chart placeholder - replace with the approved exhibit",16,True);return s
    from pptx.dml.color import RGBColor
    s=prs.slides.add_slide(prs.slide_layouts[6]);text(s,.75,1.0,12,1,title,36,True);text(s,.8,2.0,10,.7,"Quarter 4 | Operating Review | 2026",22);bar=s.shapes.add_shape(1,Inches(.8),Inches(3.0),Inches(3),Inches(.45));bar.fill.solid();bar.fill.fore_color.rgb=RGBColor(80,80,80)
    s=prs.slides.add_slide(prs.slide_layouts[6]);text(s,.65,.35,12,.55,"Executive Summary",26,True);text(s,.65,1.0,5.1,.75,"Validated operating measures and supporting evidence.",15)
    if actor=="a":
        rows=[["Supplier","Gross","Deduction","Net Payable"]]+[[x["supplier_id"],f"${x['gross_amount']:,.2f}","$0.00",f"${x['gross_amount']:,.2f}"] for x in SUPPLIERS]
    else:
        rows=[["Channel","Spend","Revenue","ROI","Alert"]]+[[x["channel_id"],f"${x['spend']:,.2f}",f"${x['revenue']:,.2f}","0.0x","No"] for x in CAMPAIGNS]
    table=s.shapes.add_table(len(rows),len(rows[0]),Inches(.65),Inches(2.0),Inches(5.2),Inches(3.7)).table
    for r,row in enumerate(rows):
        for c,val in enumerate(row):table.cell(r,c).text=val;table.cell(r,c).text_frame.paragraphs[0].font.size=Pt(10)
    text(s,6.1,1.65,6.35,3.9,"Insert approved executive exhibit",16,True)
    slide("Performance Overview","Validated source data, reconciled operating measures, and visual exhibits for leadership review.")
    slide("Drivers and Variance","Key drivers, month-over-month movement, and the implications for the next operating cycle.")
    slide("Exceptions and Controls","Document the items requiring follow-up, the supporting evidence, and the owner for each action.")
    slide("Outlook and Actions","Translate the quarter's evidence into measurable owners, dates, and operating commitments.")
    s=slide("Appendix and Notes","Source notes, assumptions, exception commentary, and the decision requested from leadership.");text(s,.65,5.9,11.8,.65,"Add the complete close-out note and preserve the supporting reconciliation reference.",14)
    prs.save(path)
def build(destination:Path):
    dst=Path(destination);root=dst if dst.name=="CONC-07" else dst/"CONC-07";g=root/"guest";ia=g/"in_a";ib=g/"in_b";oa=g/"out_a";ob=g/"out_b"
    (ia/"qc_sheets").mkdir(parents=True,exist_ok=True);(ib/"allowances").mkdir(parents=True,exist_ok=True);(oa).mkdir(parents=True,exist_ok=True);(ob).mkdir(parents=True,exist_ok=True)
    exp={"suppliers":SUPPLIERS,"campaigns":CAMPAIGNS,"supplier_chart_hashes":{},"campaign_chart_hashes":{},"supplier_qc_hashes":{},"brand_a":SUP_COLOR,"brand_b":CAM_COLOR}
    for x in SUPPLIERS:
        card(ia/f"qc_sheets/{x['supplier_id']}.png",f"Quality Review | {x['supplier_id']}",[("Gross invoice",f"${x['gross_amount']:,.2f}"),("Defect deduction",f"${x['deduction']:,.2f}"),("Finding",x['reason'])])
        exp["supplier_qc_hashes"][x["supplier_id"]]=hashlib.sha256((ia/f"qc_sheets/{x['supplier_id']}.png").read_bytes()).hexdigest()
    swatch(ia/"brand_swatch_a.png",SUP_COLOR);swatch(ib/"brand_swatch_b.png",CAM_COLOR)
    (ia/"review_spec_a.txt").write_text("Q4 Supplier Review — required design\nUse a restrained enterprise green accent (#2E7D32). Preserve seven slides. Include the six-vendor settlement table on slide 2, with gross, deduction, and net payable. Replace chart placeholders on slides 3–5 with the three downloaded supplier exhibits in the same order as their filenames. Slide 6 must explain the two dispute deductions and cite SUP-02 and SUP-05. Slide 7 must include this note in full: Reconcile the two disputed freight and transit deductions with the supplier owners before the next payment run. Source: Q4 settlement batch review. Keep every exhibit within slide bounds and clear of text. Export a seven-page PDF.\n",encoding="utf-8")
    with (ia/"supplier_master.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(["supplier_id","gross_amount","invoice_reference"])
        for i,x in enumerate(SUPPLIERS,1):w.writerow([x["supplier_id"],f"{x['gross_amount']:.2f}",f"INV-Q4-{800+i}"])
    for n,vals in zip(SUP_CHARTS,([x["net_payable"] for x in SUPPLIERS],[x["deduction"] for x in SUPPLIERS],[x["gross_amount"] for x in SUPPLIERS])):
        p=ia/f"{n}.png";chart(p,n.replace("_"," ").title(),[x["supplier_id"] for x in SUPPLIERS],vals,SUP_COLOR);exp["supplier_chart_hashes"][n]=hashlib.sha256(p.read_bytes()).hexdigest()
    (ib/"campaign_spend.csv").write_text("channel_id,spend,budget_cap\n"+"".join(f"{x['channel_id']},{x['spend']:.2f},{x['budget']:.2f}\n" for x in CAMPAIGNS),encoding="utf-8")
    for x in ALLOWANCES:card(ib/f"allowances/{x['id']}.png",f"Expense Allowance | {x['id']}",[("Verification code",x["token"]),("Eligible amount",f"${x['amount']:.2f}"),("Status","Approved for quarter-close review")],CAM_COLOR)
    (ib/"postmortem_spec_b.txt").write_text("Promo Postmortem — required design\nUse a restrained enterprise blue accent (#1565C0). Preserve seven slides. Put the six-channel KPI table on slide 2. Slide 3 must show channel exhibits 1 and 2 in that order; slide 4 must show exhibit 3. Replace the three figure placeholders with the downloaded AdPulse exhibits. Slide 5 must highlight budget-overrun alerts for CH-02 and CH-04. Slide 6 must summarize the two mobile landing-page checks. Slide 7 must include this note in full: Review the two over-cap channels with the regional owners, then carry the validated creative tests into the next planning cycle. Source: Q4 campaign postmortem. Keep all exhibit bounds within the slide and clear of text. Export a seven-page PDF.\n",encoding="utf-8")
    for n,vals in zip(CAM_CHARTS,([x["roi"]*100 for x in CAMPAIGNS],[x["spend"]-x["budget"] for x in CAMPAIGNS],[x["revenue"] for x in CAMPAIGNS])):
        p=ib/f"{n}.png";chart(p,n.replace("_"," ").title(),[x["channel_id"] for x in CAMPAIGNS],vals,CAM_COLOR);exp["campaign_chart_hashes"][n]=hashlib.sha256(p.read_bytes()).hexdigest()
    for i,(title,body) in enumerate((("LP-1 | Spring Essentials",["Clear product hierarchy","Readable offer","Single primary action"]),("LP-2 | Weekend Travel",["Compact itinerary","Accessible booking","Responsive supporting content"])),1):
        p=ib/f"mobile_lp_{i}.png";mobile(p,title,body,CAM_COLOR);exp.setdefault("mobile_hashes",{})[f"LP-{i}"]=hashlib.sha256(p.read_bytes()).hexdigest()
    # Visible values are rendered in the chart image and intentionally absent from HTML labels/API text.
    for x in CAMPAIGNS:
        p=ib/f"roi_{x['channel_id']}.png";card(p,f"AdPulse {x['channel_id']}",[("Peak ROI",f"{x['roi']:.1f}x"),("Budget alert","Review" if x["alert_flag"] else "Within plan")],CAM_COLOR);exp.setdefault("roi_image_hashes",{})[x["channel_id"]]=hashlib.sha256(p.read_bytes()).hexdigest()
    deck(oa/"Q4_Supplier_Review.pptx","Q4 Supplier Review", "a");deck(ob/"Promo_Postmortem.pptx","Q4 Promo Postmortem","b")
    exp["allowances"]=ALLOWANCES;exp["supplier_ids"]=[x["supplier_id"] for x in SUPPLIERS];exp["campaign_ids"]=[x["channel_id"] for x in CAMPAIGNS];exp["supplier_exceptions"]={x["supplier_id"]:x["reason"] for x in SUPPLIERS if x["has_dispute"]};exp["a_note"]="Reconcile the two disputed freight and transit deductions with the supplier owners before the next payment run. Source: Q4 settlement batch review.";exp["b_note"]="Review the two over-cap channels with the regional owners, then carry the validated creative tests into the next planning cycle. Source: Q4 campaign postmortem."
    (root/"private").mkdir(parents=True,exist_ok=True);(root/"private/expected.json").write_text(json.dumps(exp,indent=2),encoding="utf-8")
    return root
if __name__=="__main__":
    import argparse;p=argparse.ArgumentParser();p.add_argument("destination",type=Path);print(build(p.parse_args().destination))
