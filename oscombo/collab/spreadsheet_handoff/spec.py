"""Frozen task contract and gold answers for Spreadsheet Handoff V0."""
from __future__ import annotations

from . import CASE_ID, CASE_VERSION, CONDITIONS

FIXTURE_NAME = "replenishment.ods"
HORIZON_MONTHS = 2
FREIGHT = 120.0
BUDGET_CAP = 3300.0

# Sales are the three latest complete months. Values are units, not currency.
SALES = (
    ("SKU-LAMP", 40, 50, 60),
    ("SKU-MUG", 65, 55, 60),
    ("SKU-CABLE", 90, 100, 110),
    ("SKU-CASE", 18, 20, 22),
)
# on hand, inbound, safety stock, case pack, unit cost (USD)
INVENTORY = (
    ("SKU-LAMP", 42, 18, 30, 10, 28.0),
    ("SKU-MUG", 50, 10, 20, 24, 7.5),
    ("SKU-CABLE", 150, 30, 50, 25, 6.4),
    ("SKU-CASE", 60, 0, 10, 20, 15.0),
)

GOLD = {
    "SKU-LAMP": {"average": 50.0, "forecast": 100.0, "target": 130.0,
                 "available": 60.0, "net": 70.0, "order": 70.0, "cost": 1960.0},
    "SKU-MUG": {"average": 60.0, "forecast": 120.0, "target": 140.0,
                "available": 60.0, "net": 80.0, "order": 96.0, "cost": 720.0},
    "SKU-CABLE": {"average": 100.0, "forecast": 200.0, "target": 250.0,
                   "available": 180.0, "net": 70.0, "order": 75.0, "cost": 480.0},
    "SKU-CASE": {"average": 20.0, "forecast": 40.0, "target": 50.0,
                 "available": 60.0, "net": 0.0, "order": 0.0, "cost": 0.0},
}
GOLD_PURCHASE_SUBTOTAL = 3160.0
GOLD_TOTAL = 3280.0
GOLD_REMAINING = 20.0

ACTOR_A_INSTRUCTION = """You are A, responsible for the demand and inventory analysis in the replenishment workbook. Review the Sales and Inventory sheets against the included data notes. In the Forecast sheet, complete the three-month average, two-month demand forecast, target stock (forecast plus safety stock), available stock (on hand plus inbound), and non-negative net requirement. Preserve every source value. Add concise cell-level evidence and mark your Forecast review complete only after checking B's proposed order quantities against your calculations. You may ask B to clarify any procurement assumption and may revise your own forecast if you find a source-data issue. Do not edit the Replenishment or Budget sheets. Save each workbook revision through the shared version service before handing off; the service permits only one active writer and rejects stale revisions. All source facts and rules are visible to both roles; messages and attachments are available when useful, with no required number or timing."""

ACTOR_B_INSTRUCTION = """You are B, responsible for procurement planning in the same replenishment workbook. Read the Sales, Inventory, and Rules sheets and use A's Forecast sheet as an auditable input. Complete the Replenishment sheet: round each positive net requirement up to the next allowed case pack, preserve zero requirements as zero, calculate extended cost, and provide a short procurement reason. Complete the Budget sheet using the stated freight and cap, and check that your order rows agree with A's forecast. If figures or assumptions do not reconcile, ask A a specific question and revise your plan after checking the latest saved workbook revision. Do not edit source sheets or the Forecast sheet. Save through the shared version service; only one actor may hold the write lease, and every commit must be based on the latest revision. All source facts are visible to you; use messages or attachments as needed, without a prescribed handoff schedule."""

SINGLE_AGENT_INSTRUCTION = """Complete the full inventory replenishment workbook. Verify the visible sales, inventory, and procurement rules; fill the Forecast, Replenishment, and Budget sheets; ensure case-pack rounding and total cost fit the budget; and perform a final cross-check. Preserve source data and use formulas where the existing layout calls for them. Save the completed workbook through the version service and verify the committed revision. No hidden evaluator state is available."""

SOURCE_RULES = (
    "Forecast horizon: the next two months.",
    "Average monthly demand: arithmetic mean of the three listed months.",
    "Target stock: forecast units plus safety stock.",
    "Available stock: on-hand units plus confirmed inbound units.",
    "Net requirement: max(target stock minus available stock, 0).",
    "Order quantity: round a positive net requirement up to an integer multiple of case pack.",
    "Extended cost: order quantity times unit cost. Procurement freight is a fixed $120.",
    "Total spend, including freight, must not exceed the $3,300 purchase cap.",
)

SINGLE_WRITER_PROTOCOL = {
    "repository": "one append-only episode-scoped ODS revision repository in all conditions",
    "lease": "one active writer lease; commit uses revision+SHA-256 compare-and-swap; stale commits are rejected",
    "handoff": "actor releases lease by commit or abandon; next actor checks out latest committed .ods",
    "desktop_is_the_only_treatment": True,
}

ROLE_BUDGET = {"steps": 240, "model_tokens": 12000, "calibrated": False}
