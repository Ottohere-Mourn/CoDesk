"""Generate fixed-name BI downloads, summit illustrations, and a 5-slide deck."""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pptx import Presentation
from pptx.util import Inches,Pt

COMBOS={"NA-Q3":{"revenues":[420000,385000,410000,442000],"adjustment":35000},
"EU-Q3":{"revenues":[321000,309000,330000,358000],"adjustment":22500},
"APAC-Q4":{"revenues":[550000,530000,580000,602000],"adjustment":41250},
"LATAM-Q4":{"revenues":[200000,216000,228000,240000],"adjustment":10750}}
ASSET_NAMES=["Summit_Keynote","Summit_TrackA","Summit_TrackB","Summit_Roadmap"]
ASSET_COLORS=["#1B8A8F","#D17B0F","#6247AA","#C2475B"]
ERRATA={"keynote_time":"09:00","keynote_speaker":"Dr. Maya Chen","track_a_time":"10:45","track_b_speaker":"Priya Nair"}
CONCLUSION="Together, these four sessions turn a year of research into practical commitments: share evidence openly, test ideas with care, design for resilient communities, and carry the work forward through measurable collaboration."

def font(sz,bold=False):
 for n in (("DejaVuSans-Bold.ttf","arialbd.ttf") if bold else ("DejaVuSans.ttf","arial.ttf")):
  try:return ImageFont.truetype(n,sz)
  except OSError:pass
 return ImageFont.load_default()
def chart(combo,vals,adjust,path):
 im=Image.new("RGB",(1280,800),"#f7f9fc");d=ImageDraw.Draw(im);d.text((55,35),f"METRICPULSE | {combo}",font=font(30,True),fill="#18334d");d.text((55,80),"Quarterly commercial performance",font=font(19),fill="#61758a")
 x0,y0,x1,y1=90,180,1185,685
 for i in range(6):
  y=y0+i*(y1-y0)/5;d.line((x0,y,x1,y),fill="#e1e7ef",width=2);d.text((32,y-9),f"{100-i*20}%",font=font(12),fill="#728196")
 width=115;gap=130;tops=[]
 for i,v in enumerate(vals):
  h=int(v/max(vals)*330);x=x0+70+i*(width+gap);y=y1-h;tops.append((x+width//2,y));d.rounded_rectangle((x,y,x+width,y1),radius=12,fill=["#1b8a8f","#3682b5","#6b65ac","#d17b0f"][i])
  d.text((x+14,y1+18),f"Q{i+1}",font=font(15,True),fill="#43536b");d.text((x+5,y-29),f"${v:,}",font=font(13),fill="#43536b")
 d.line(tops,fill="#d14c48",width=4)
 for x,y in tops:d.ellipse((x-7,y-7,x+7,y+7),fill="#d14c48")
 d.rounded_rectangle((910,115,1200,165),radius=9,fill="#fff2d6",outline="#e7a63d",width=2)
 # Pixel-only target adjustment; it is deliberately absent from CSV and HTML text.
 d.text((930,126),f"Target Adjustment  ${adjust:,}",font=font(19,True),fill="#704600")
 im.save(path,format="PNG",optimize=True)
def illustration(name,color,path):
 im=Image.new("RGB",(1200,760),"#f7f9fc");d=ImageDraw.Draw(im);d.rounded_rectangle((20,20,1180,740),radius=32,fill="white",outline="#d8e1ea",width=3)
 d.rectangle((20,20,1180,175),fill=color);d.text((65,58),name.replace("_"," "),font=font(42,True),fill="white")
 if name=="Summit_Keynote":
  for i,(x,h) in enumerate(((180,260),(330,375),(480,310),(630,430),(780,355))):d.rounded_rectangle((x,590-h,x+95,590),radius=12,fill=color);d.text((x+22,615),f"{i+1}",font=font(18,True),fill="#53677d")
  d.line((170,410,870,300),fill="#20354b",width=5)
 elif name=="Summit_TrackA":
  d.ellipse((310,260,870,670),fill="#eaf5f5",outline=color,width=8);d.ellipse((450,360,730,620),fill=color);d.text((445,430),"LEARN",font=font(38,True),fill="white")
 elif name=="Summit_TrackB":
  for i in range(4):d.rounded_rectangle((130+i*230,300,330+i*230,560),radius=18,fill=color if i%2==0 else "#f2eafc");d.line((230+i*230,255,230+i*230,300),fill="#324b63",width=5)
 else:
  pts=[(135,560),(360,470),(580,390),(820,300),(1050,210)];d.line(pts,fill=color,width=13,joint="curve")
  for x,y in pts:d.ellipse((x-18,y-18,x+18,y+18),fill="#fff",outline=color,width=7)
 d.text((70,690),"SUMMIT 2026  |  IDEAS INTO ACTION",font=font(18,True),fill="#5b6b7b");im.save(path,format="PNG",optimize=True)
def brochure(path):
 prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
 def tx(slide,x,y,w,h,text,size=18,bold=False):
  sh=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=sh.text_frame;tf.word_wrap=True;tf.text=text
  for p in tf.paragraphs:
   for r in p.runs:r.font.size=Pt(size);r.font.bold=bold
  return sh
 def slide(title,body):
  s=prs.slides.add_slide(prs.slide_layouts[6]);tx(s,.65,.38,12,.45,title,25,True);tx(s,.65,.95,5.2,4.8,body,16);tx(s,6.1,1.55,6.5,4.4,"Graphic placeholder",16);return s
 s=prs.slides.add_slide(prs.slide_layouts[6]);tx(s,.8,1.45,11,1.2,"HORIZON 2026",40,True);tx(s,.85,2.8,10,.8,"Research, systems, and resilient communities",23)
 s=slide("Day 1 Agenda","The summit convenes four sessions across research, infrastructure, community resilience, and practical collaboration.")
 rows=[["Time","Session","Speaker"],["09:15","Opening Keynote","Dr. Lena Ortiz"],["10:30","Track A: Systems","Arun Patel"],["11:00","Track B: Communities","Luis Gomez"],["14:30","Closing Forum","Maya Chen"]]
 table=s.shapes.add_table(len(rows),3,Inches(.65),Inches(2.1),Inches(5.1),Inches(2.6)).table
 for r,row in enumerate(rows):
  for c,val in enumerate(row):table.cell(r,c).text=val;table.cell(r,c).text_frame.paragraphs[0].font.size=Pt(13)
 slide("Keynote: Measurable Progress","Opening perspective on dependable data, practical service design, and evidence that guides decisions.")
 slide("Track A: Responsible Infrastructure","Methods for building systems that remain understandable, measurable, and dependable under change.")
 s=slide("Track B: Resilient Communities","Learn from local experiments and turn shared evidence into inclusive, durable commitments.")
 tx(s,.65,5.95,11.9,.45,"Add a concluding statement here.",13)
 prs.save(path)
def build(destination:Path):
 destination=Path(destination);root=destination if destination.name=="CONC-06" else destination/"CONC-06";guest=root/"guest";bi=guest/"in_a/bi";assets=guest/"in_b/assets";bi.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
 expected={"bi":{},"assets":{}}
 for combo,info in COMBOS.items():
  csvp=bi/f"{combo}.csv"
  with csvp.open("w",newline="",encoding="utf-8") as f:
   w=csv.writer(f,lineterminator="\n");w.writerow(["period","revenue"]);w.writerows([(f"Month-{i+1}",v) for i,v in enumerate(info["revenues"])])
  png=bi/f"{combo}.png";chart(combo,info["revenues"],info["adjustment"],png)
  expected["bi"][combo]={"csv_total":sum(info["revenues"]),"target_adjustment":info["adjustment"],"variance":sum(info["revenues"])-info["adjustment"],"csv_sha256":hashlib.sha256(csvp.read_bytes()).hexdigest(),"png_sha256":hashlib.sha256(png.read_bytes()).hexdigest()}
 for name,color in zip(ASSET_NAMES,ASSET_COLORS):
  p=assets/f"{name}.png";illustration(name,color,p);expected["assets"][name]={"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"color":color}
 agenda=("Brochure errata - corrected Day 1 agenda values:\n"
  "Keynote session time: replace 09:15 with 09:00.\n"
  "Keynote speaker: replace Dr. Lena Ortiz with Dr. Maya Chen.\n"
  "Track A session time: replace 10:30 with 10:45.\n"
  "Track B speaker: replace Luis Gomez with Priya Nair.\n\n"
  "Insert Summit_Keynote on page 2, Summit_TrackA on page 3, Summit_TrackB on page 4, and Summit_Roadmap on page 5.\n\n"
  f"Page 5 concluding statement (include in full):\n{CONCLUSION}\n")
 (guest/"in_b/agenda_errata.txt").write_text(agenda,encoding="utf-8")
 deck=guest/"out_b/Summit_Brochure.pptx";deck.parent.mkdir(parents=True,exist_ok=True);brochure(deck)
 expected["agenda"]=ERRATA;expected["conclusion"]=CONCLUSION;expected["deck_sha256"]=hashlib.sha256(deck.read_bytes()).hexdigest()
 (root/"private").mkdir(parents=True,exist_ok=True);(root/"private/expected.json").write_text(json.dumps(expected,indent=2),encoding="utf-8")
 return root
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("destination",type=Path);print(build(p.parse_args().destination))
