"""Frozen V0 task data and contract for CDD-RECON-001."""
from __future__ import annotations

CASE_ID = "CDD-RECON-001"
CASE_VERSION = "0.2.1"

SALES = (
    ("Q1", "North", 100), ("Q1", "South", 80), ("Q1", "West", 60),
    ("Q2", "North", 110), ("Q2", "South", 90), ("Q2", "West", 70),
    ("Q3", "North", 120), ("Q3", "South", 95), ("Q3", "West", 85),
    ("Q4", "North", 130), ("Q4", "South", 105), ("Q4", "West", 95),
)
COSTS = (
    ("Q1", "North", 55, 5, 2), ("Q1", "South", 44, 4, 2), ("Q1", "West", 33, 3, 2),
    ("Q2", "North", 60, 5, 3), ("Q2", "South", 50, 5, 3), ("Q2", "West", 38, 4, 4),
    ("Q3", "North", 66, 6, 4), ("Q3", "South", 52, 5, 2), ("Q3", "West", 47, 7, 18),
    ("Q4", "North", 72, 6, 3), ("Q4", "South", 58, 5, 4), ("Q4", "West", 51, 5, 5),
)
QUARTERS = ("Q1", "Q2", "Q3", "Q4")
REGIONS = ("North", "South", "West")

# Amounts are USD thousands; margins and growth values are fractions.
GOLD_QUARTERS = {
    "Q1": {"revenue": 240, "cogs": 132, "fulfillment": 12, "promotion": 6,
           "total_cost": 150, "operating_profit": 90, "gross_margin": 0.45, "operating_margin": 0.375},
    "Q2": {"revenue": 270, "cogs": 148, "fulfillment": 14, "promotion": 10,
           "total_cost": 172, "operating_profit": 98, "gross_margin": 122 / 270, "operating_margin": 98 / 270},
    "Q3": {"revenue": 300, "cogs": 165, "fulfillment": 18, "promotion": 24,
           "total_cost": 207, "operating_profit": 93, "gross_margin": 0.45, "operating_margin": 0.31},
    "Q4": {"revenue": 330, "cogs": 181, "fulfillment": 16, "promotion": 12,
           "total_cost": 209, "operating_profit": 121, "gross_margin": 149 / 330, "operating_margin": 121 / 330},
}
GOLD_REGIONAL_PROFIT = {
    "Q1": {"North": 38, "South": 30, "West": 22},
    "Q2": {"North": 42, "South": 32, "West": 24},
    "Q3": {"North": 44, "South": 36, "West": 13},
    "Q4": {"North": 49, "South": 38, "West": 34},
}
GOLD_RECONCILIATION = {
    ("quarter_delta", "revenue"): 30,
    ("quarter_delta", "cogs"): 17,
    ("quarter_delta", "fulfillment"): 4,
    ("quarter_delta", "promotion"): 14,
    ("quarter_delta", "total_cost"): 35,
    ("quarter_delta", "operating_profit"): -5,
    ("quarter_delta", "revenue_growth"): 30 / 270,
    ("quarter_delta", "profit_growth"): -5 / 98,
    ("quarter_delta", "margin_change_pp"): (0.31 - 98 / 270) * 100,
    ("region_delta", "North"): 2,
    ("region_delta", "South"): 4,
    ("region_delta", "West"): -11,
    ("west_delta", "revenue"): 15,
    ("west_delta", "promotion"): 14,
    ("west_delta", "operating_profit"): -11,
}

ERRORS = {
    "R1": {"kind": "numeric transcription", "wrong": 310, "correct": 300,
           "locations": ("slide1_q3_revenue", "slide2_q3_revenue")},
    "R2": {"kind": "metric definition", "wrong_label": "Gross Margin", "wrong_value": 0.31,
           "correct_gross": 0.45, "correct_operating": 0.31},
    "R3": {"kind": "unsupported causal attribution",
           "wrong_claim": "West discount campaign caused the Q3 profit decline.",
           "required_status": "CAUSALITY NOT ESTABLISHED"},
}

AGENT_A_INSTRUCTION = """You are the Data Verifier. The authoritative workbook is quarterly_authority.ods. Verify its raw Sales and Costs sheets and existing basic quarterly summary. In your output copy, preserve those sheets and fill the blank Reconciliation sheet using the existing five-column header: Section, Metric, Value, Unit, Evidence. Include one row per required key: quarter_delta/revenue, cogs, fulfillment, promotion, total_cost, operating_profit, revenue_growth, profit_growth, margin_change_pp; region_delta/North, South, West; west_delta/revenue, promotion, operating_profit; evidence_boundary/causality. Use exact units USD_k, fraction, percentage_points, or status as appropriate. Values must be numerically correct; Evidence should identify a relevant sheet/quarters/region or a traceable cell reference. Use traceable formulas or cell references where feasible. You may inspect the draft presentation but must not edit or save the Impress deliverable. Publish a verified analysis revision through the shared message/artifact interface and respond to specific evidence questions when useful. You may start with partial verified findings; there is no required message count or handoff time. Do not edit authoritative input files or claim causality unsupported by the data."""

AGENT_B_INSTRUCTION = """You are the Report Editor. quarterly_authority.ods is authoritative; management_draft.odp is an unfinished draft whose inconsistencies are not marked. You can read all source data and the workbook, and you are the sole writer of the Impress output. Review and correct the draft, preserve its correct content, and complete its three-slide management report, especially the Q2-to-Q3 regional/cost explanation on slide 3. Distinguish gross margin from operating margin and do not overstate causality. You may independently verify data, read the Data Verifier's published revision, or ask a specific question if evidence is unclear. Cite the analysis revision/hash used in your final deck. No fixed message count, handoff time, GUI action, or conflict is required."""

SINGLE_AGENT_INSTRUCTION = """You are completing the whole Collaborative Reconciliation case alone. Verify the authoritative Calc workbook, complete its Reconciliation sheet, review and correct the unfinished Impress draft, preserve correct content, and save both required outputs. Use traceable calculations, distinguish gross and operating margin, qualify unsupported causal claims, and record the analysis revision used by the deck. No hidden evaluator state is available."""

CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
OUTPUTS = {"A": "outputs/agent_A/verified_analysis.ods", "B": "outputs/agent_B/final_management_brief.odp"}

# Model-calibration budget raised after the initial 60-step episodes all ended
# at max_steps. This is a per-role diagnostic cap, not a calibrated sufficiency
# claim. Single-Agent whole-case budget is the sum of A and B; collaborative
# conditions retain the same per-role caps.
ROLE_BUDGET = {"A": {"steps": 240, "model_tokens": 12000},
               "B": {"steps": 240, "model_tokens": 12000}}
TOTAL_MODEL_TOKEN_BUDGET = sum(v["model_tokens"] for v in ROLE_BUDGET.values())
FIXTURE_NAMES = {
    "authority": "quarterly_authority.ods",
    "draft": "management_draft.odp",
    "brief": "case_brief.md",
}
