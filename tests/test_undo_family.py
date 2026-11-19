from tasks.mechanism_expansion_v1 import undo_family as uf
from tasks.mechanism_expansion_v1.undo_family import CASES,TASKS,TASK_VERSION,_rows,NS
import xml.etree.ElementTree as ET

def make_xml(case, data_rows=None):
 s=CASES[case]; data_rows=data_rows or s["rows"]
 root=ET.Element("{%s}document-content"%NS["office"])
 body=ET.SubElement(root,"{%s}body"%NS["office"]); sheet=ET.SubElement(body,"{%s}spreadsheet"%NS["office"])
 tab=ET.SubElement(sheet,"{%s}table"%NS["table"])
 for row in [s["headers"]]+data_rows:
  tr=ET.SubElement(tab,"{%s}table-row"%NS["table"])
  for value in row:
   cell=ET.SubElement(tr,"{%s}table-cell"%NS["table"])
   p=ET.SubElement(cell,"{%s}p"%NS["text"]); p.text=value
 return ET.tostring(root)

def test_four_cases_have_distinct_practical_workflows_and_same_undo_contract():
 assert set(CASES)=={"mech06","mech07","mech08","mech09"}
 assert len({v["title"] for v in CASES.values()})==4
 assert all("Ctrl+Z" in v["a_task"] for v in CASES.values())
 assert all(v["a_id"]!=v["b_id"] for v in CASES.values())
 assert TASK_VERSION=="0.5.0"
 assert all("pre-staged" in v["a_task"] for v in CASES.values())
 assert all("Do not type" in v["a_task"] for v in CASES.values())
 assert all(len(v["a_verify_cols"])>=4 and v["a_temp_col"] not in v["a_verify_cols"] for v in CASES.values())
 assert all("Do not use Undo" in v["b_task"] for v in CASES.values())
 assert all(len(v["b_values"])==1 for v in CASES.values())

def test_fixture_rows_parse_and_initial_state_fails_target_oracle():
 for cid,s in CASES.items():
  rows=_rows(make_xml(cid),len(s["headers"]))
  assert rows==[s["headers"]]+s["rows"]
  assert len({r[0] for r in rows[1:]})==len(s["rows"])

def test_oracles_distinguish_positive_and_global_undo_negative(monkeypatch):
 class FakeEnv: pass
 for cid,s in CASES.items():
  base={r[0]:r[:] for r in s["rows"]}
  # MA-ID positive: setup stages the edit; A undoes it, marks review, B writes.
  pos={k:v[:] for k,v in base.items()}
  pos[s["a_id"]][s["a_mark_col"]]=s["a_mark"]
  for col,value in s["b_values"].items(): pos[s["b_id"]][col]=value
  monkeypatch.setattr(uf,"_read_guest_xml",lambda env,case,rows=pos:{"xml":make_xml(case,[rows[r[0]] for r in CASES[case]["rows"]])})
  assert uf.evaluate(FakeEnv(),cid,"A")["score"]==1.0
  assert uf.evaluate(FakeEnv(),cid,"B")["score"]==1.0
  # Fixed negative interleave: B commits after setup, then A's one Undo
  # removes B's field while leaving A's staged value and review marker.
  neg={k:v[:] for k,v in base.items()}
  neg[s["a_id"]][s["a_temp_col"]]=s["a_temp"]
  neg[s["a_id"]][s["a_mark_col"]]=s["a_mark"]
  for col,value in s["b_values"].items(): neg[s["b_id"]][col]=base[s["b_id"]][col]
  monkeypatch.setattr(uf,"_read_guest_xml",lambda env,case,rows=neg:{"xml":make_xml(case,[rows[r[0]] for r in CASES[case]["rows"]])})
  a=uf.evaluate(FakeEnv(),cid,"A"); b=uf.evaluate(FakeEnv(),cid,"B")
  assert a["score"]==0.0 and a["checks"]["temporary_edit_undone"] is False
  assert b["score"]==0.0 and b["checks"]["b_target_fields_saved"] is False

def test_task_objects_reference_current_instructions():
 for cid,s in CASES.items():
  assert TASKS[cid]["A"]==s["a_task"]
  assert TASKS[cid]["B"]==s["b_task"]
