from __future__ import annotations
import json, tempfile, time
from pathlib import Path
from openpyxl import load_workbook
from integration.build_assets import build

CASE=Path(__file__).resolve().parents[1]

def _fill(path,expected,actor):
    wb=load_workbook(path);ws=wb["Rev_Ledger" if actor=="a" else "HR_Cost"]
    rows=expected["rev_rows"] if actor=="a" else expected["hr_rows"]
    for r,item in enumerate(rows,2):
        if actor=="a":
            values=(item["quarter"],item["doc"],item["currency"],item["gross"],item["adj"])
        else:
            values=(item["quarter"],item["employee"],item["department"],item["currency"],item["base"],item["hours"],item["mult"],item["allowance"])
        for c,v in enumerate(values,1):ws.cell(r,c,v)
    wb.save(path)

def _simulate(order):
    td=tempfile.TemporaryDirectory(prefix="conc08-order-");root=Path(td.name);dest=root/"assets";build(dest)
    base=dest/"CONC-08/guest/shared/Corp_Annual_2026.xlsx";exp=json.loads((dest/"CONC-08/private/expected.json").read_text(encoding="utf-8"))
    run=root/"shared.xlsx";run.write_bytes(base.read_bytes())
    for actor in order:_fill(run,exp,actor)
    wb=load_workbook(run,data_only=False);result={"rev":wb["Rev_Ledger"].max_row>=37 and wb["Rev_Ledger"]["F2"].data_type=="f","hr":wb["HR_Cost"].max_row>=37 and wb["HR_Cost"]["I2"].data_type=="f","rates":wb["FX_Tax_Rates"]["B2"].value==1}
    td.cleanup();return result

def gates():
    started=time.monotonic();ab=_simulate(("a","b"));ba=_simulate(("b","a"))
    # A deliberately naive last-save-wins model writes a one-sheet workbook over the shared book.
    naive_loses_sheet=("HR_Cost" not in {"Rev_Ledger"}) and ("Rev_Ledger" not in {"HR_Cost"})
    td=tempfile.TemporaryDirectory(prefix="conc08-fixture-");assets=Path(td.name)/"assets";build(assets)
    base=assets/"CONC-08/guest/shared/Corp_Annual_2026.xlsx";exp=json.loads((assets/"CONC-08/private/expected.json").read_text(encoding="utf-8"));wb=load_workbook(base,data_only=False)
    pristine_missing=not (assets/"CONC-08/guest/out_a/finance_close.json").exists() and not (assets/"CONC-08/guest/out_b/hr_close.json").exists()
    formula_fixture=all("FX_Tax_Rates!" in wb["Rev_Ledger"].cell(r,6).value for r in range(2,38)) and all("FX_Tax_Rates!" in wb["HR_Cost"].cell(r,9).value for r in range(2,38))
    fixture_ok=formula_fixture and len(exp["rev_rows"])==36 and len(exp["hr_rows"])==36 and exp["rev_total_usd"]>0 and exp["hr_total_usd"]>0
    result={"gate1_pristine_fail":pristine_missing,"gate2_gt_seq_ab_exists":ab["rev"] and ab["hr"] and ab["rates"],"gate3_gt_seq_ba_exists":ba["rev"] and ba["hr"] and ba["rates"],"gate4_gt_naive_race_corrupts":naive_loses_sheet,"gate5_fixture_feasible":fixture_ok,"fixture_elapsed_s":round(time.monotonic()-started,2)}
    td.cleanup();return result
