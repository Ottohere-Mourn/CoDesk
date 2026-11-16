import json,sys
from pathlib import Path
import pytest
ROOT=Path("/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112")
sys.path.insert(0,str(ROOT/"tasks/paragui"))
from build_v456 import DATA,build
from pg_v456_oracle import checks
@pytest.mark.parametrize("case",["v7","v8","v9","v10","v11","v12","v13","v14","v15","v16","v17","v18","v19","v20","v21","v22","v23","v24","v25","v26","v27","v28","v29","v30","v31","v32","v33"])
def test_joint_positive_and_fixture_build(tmp_path,case):
 out=tmp_path/case;build(case,out)
 assert (out/f"app_{case}.py").is_file()
 state={"items":[],"desk":{"active_id":"","active_panel":"A"}}
 for row in DATA[case]["items"]:
  state["items"].append({"id":row["id"],"kind":row["kind"],"facts":"{}","data_a":json.dumps(DATA[case]["expected"]["A"][row["id"]]),"data_b":json.dumps(DATA[case]["expected"]["B"][row["id"]])})
 for panel in ("A","B"):
  result,score=checks(state,DATA[case]["expected"],panel,case)
  assert score==1.0,result
@pytest.mark.parametrize("case,panel",[(c,p) for c in ("v7","v8","v9","v10","v11","v12","v13","v14","v15","v16","v17","v18","v19","v20","v21","v22","v23","v24","v25","v26","v27","v28","v29","v30","v31","v32","v33") for p in ("A","B")])
def test_missing_record_output_is_scored_as_failure(case,panel):
 expected=DATA[case]["expected"];state={"items":[],"desk":{"active_id":"","active_panel":panel}}
 for row in DATA[case]["items"]:
  state["items"].append({"id":row["id"],"kind":row["kind"],"facts":"{}","data_a":json.dumps(expected["A"][row["id"]]),"data_b":json.dumps(expected["B"][row["id"]])})
 target=next(iter(expected[panel]));row=next(x for x in state["items"] if x["id"]==target)
 row["data_"+panel.lower()]="{}"
 _,score=checks(state,expected,panel,case)
 assert score==pytest.approx((len(expected[panel])-1)/len(expected[panel]))


@pytest.mark.parametrize(
    "case,panel,key,alternate",
    [
        ("v23", "A", "reserve_amount", "8,600.00"),
        ("v27", "A", "recommended_award", "USD 12,000"),
    ],
)
def test_currency_amount_formatting_is_normalized(tmp_path,case,panel,key,alternate):
    expected=DATA[case]["expected"]
    state={"items":[],"desk":{"active_id":"","active_panel":panel}}
    for row in DATA[case]["items"]:
        state["items"].append({
            "id":row["id"],"kind":row["kind"],"facts":"{}",
            "data_a":json.dumps(expected["A"][row["id"]]),
            "data_b":json.dumps(expected["B"][row["id"]]),
        })
    row=state["items"][0]
    actual=json.loads(row["data_"+panel.lower()])
    actual[key]=alternate
    row["data_"+panel.lower()]=json.dumps(actual)
    _,score=checks(state,expected,panel,case)
    assert score==1.0

@pytest.mark.parametrize(
    "case,panel,key,wrong",
    [
        ("v23", "A", "reserve_amount", "USD 8,601"),
        ("v27", "A", "recommended_award", "12001"),
    ],
)
def test_currency_amount_normalization_keeps_wrong_amount_a_failure(case,panel,key,wrong):
    expected=DATA[case]["expected"]
    state={"items":[],"desk":{"active_id":"","active_panel":panel}}
    for row in DATA[case]["items"]:
        state["items"].append({
            "id":row["id"],"kind":row["kind"],"facts":"{}",
            "data_a":json.dumps(expected["A"][row["id"]]),
            "data_b":json.dumps(expected["B"][row["id"]]),
        })
    row=state["items"][0]
    actual=json.loads(row["data_"+panel.lower()])
    actual[key]=wrong
    row["data_"+panel.lower()]=json.dumps(actual)
    _,score=checks(state,expected,panel,case)
    assert score==0.0


@pytest.mark.parametrize("actual,score",[
    ("12/01/2026",1.0),
    ("2026/12/01",1.0),
    ("12/02/2026",0.0),
])
def test_v27_us_and_iso_schedule_dates_are_compared_semantically(actual,score):
    expected=DATA["v27"]["expected"]
    state={"items":[],"desk":{"active_id":"","active_panel":"B"}}
    for row in DATA["v27"]["items"]:
        state["items"].append({
            "id":row["id"],"kind":row["kind"],"facts":"{}",
            "data_a":json.dumps(expected["A"][row["id"]]),
            "data_b":json.dumps(expected["B"][row["id"]]),
        })
    row=state["items"][0]
    actual_b=json.loads(row["data_b"])
    actual_b["scheduled_date"]=actual
    row["data_b"]=json.dumps(actual_b)
    _,got=checks(state,expected,"B","v27")
    assert got==score
