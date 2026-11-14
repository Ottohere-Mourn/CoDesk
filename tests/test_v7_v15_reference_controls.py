import json,sys
from pathlib import Path
import pytest
ROOT=Path("/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112")
sys.path.insert(0,str(ROOT/"tasks/paragui"))
from build_v456 import DATA,build
from pg_v456_oracle import checks
@pytest.mark.parametrize("case",["v7","v8","v9","v10","v11","v12","v13","v14","v15"])
def test_joint_positive_and_fixture_build(tmp_path,case):
 out=tmp_path/case;build(case,out)
 assert (out/f"app_{case}.py").is_file()
 state={"items":[],"desk":{"active_id":"","active_panel":"A"}}
 for row in DATA[case]["items"]:
  state["items"].append({"id":row["id"],"kind":row["kind"],"facts":"{}","data_a":json.dumps(DATA[case]["expected"]["A"][row["id"]]),"data_b":json.dumps(DATA[case]["expected"]["B"][row["id"]])})
 for panel in ("A","B"):
  result,score=checks(state,DATA[case]["expected"],panel,case)
  assert score==1.0,result
@pytest.mark.parametrize("case,panel",[(c,p) for c in ("v7","v8","v9","v10","v11","v12","v13","v14","v15") for p in ("A","B")])
def test_missing_record_output_is_scored_as_failure(case,panel):
 expected=DATA[case]["expected"];state={"items":[],"desk":{"active_id":"","active_panel":panel}}
 for row in DATA[case]["items"]:
  state["items"].append({"id":row["id"],"kind":row["kind"],"facts":"{}","data_a":json.dumps(expected["A"][row["id"]]),"data_b":json.dumps(expected["B"][row["id"]])})
 target=next(iter(expected[panel]));row=next(x for x in state["items"] if x["id"]==target)
 row["data_"+panel.lower()]="{}"
 _,score=checks(state,expected,panel,case)
 assert score==pytest.approx((len(expected[panel])-1)/len(expected[panel]))
