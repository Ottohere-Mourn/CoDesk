"""Public task contract and deterministic acceptance fixture."""
from __future__ import annotations

CASE_ID = "CDD-BV-LITE-001"
CASE_VERSION = "1.4.4"
PAIR_MAX_STEPS = 12
CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
DATA_FILE = "data/orders.json"
FILTER_FILE = "filtering.py"
APP_FILE = "static/app.js"
PROTECTED_FILES = (
    "README.md", "requirements.md", "data/orders.json", "static/index.html",
    "static/style.css", "static/app.js", "tests/public_test_plan.json",
)

# Public, synthetic rows: each field is visible in the app and in the project.
ORDERS = (
    {"order_id": "NW-2401", "customer": "Avery Chen", "region": "North", "status": "Processing", "total_cents": 12900},
    {"order_id": "NW-2402", "customer": "Dana Ruiz", "region": "West", "status": "Shipped", "total_cents": 8750},
    {"order_id": "NW-2403", "customer": "Dana Ruiz", "region": "West", "status": "Processing", "total_cents": 4310},
    {"order_id": "NW-2404", "customer": "Mira Patel", "region": "South", "status": "Delivered", "total_cents": 22200},
    {"order_id": "NW-2405", "customer": "Noah Kim", "region": "West", "status": "Processing", "total_cents": 6199},
    {"order_id": "NW-2406", "customer": "Dana Ruiz", "region": "North", "status": "Delivered", "total_cents": 10000},
    {"order_id": "NW-2407", "customer": "Avery Chen", "region": "West", "status": "Shipped", "total_cents": 14750},
    {"order_id": "NW-2408", "customer": "Mira Patel", "region": "West", "status": "Processing", "total_cents": 3900},
)
STATUSES = ("All", "Processing", "Shipped", "Delivered")

# Hidden expected IDs for the evaluator. Actors receive the descriptions and
# can inspect all rows; expected result membership is not handed to them.
ORACLE_CASES = (
    {"query": "  dAnA ", "status": "Processing", "ids": ("NW-2403",)},
    {"query": "west", "status": "Processing", "ids": ("NW-2403", "NW-2405", "NW-2408")},
    {"query": "NW-2402", "status": "Processing", "ids": ()},
    {"query": "", "status": "Shipped", "ids": ("NW-2402", "NW-2407")},
    {"query": "Dana", "status": "All", "ids": ("NW-2402", "NW-2403", "NW-2406")},
    {"query": "", "status": "All", "ids": tuple(row["order_id"] for row in ORDERS)},
)

ACTOR_A_INSTRUCTION = """You are A, the OrderDesk developer. In the open GUI editor, repair filtering.py so search text and selected status combine conjunctively. Search is trimmed and case-insensitive across order ID, customer and region; All means no status restriction. Do not edit any other file. B is testing the live browser. Wait for B's concrete failing Dana + Processing observation before editing so the baseline is recorded. Finish all edits and save the file before telling B what changed. Once you tell B the saved revision is ready for retest, do not edit the file again. Use only the GUI editor and collaboration tools, not Terminal or scripts."""

ACTOR_B_INSTRUCTION = """You are B, the browser QA analyst. The open browser already has Dana in its search field and Processing selected; these prepared controls have not been submitted. Focus the search field and press Enter to reproduce the defect. Send A the concrete live result, including the wrong order IDs. While A repairs the code, stay in the browser and replace the search text with NW-2402, keeping Processing selected. Prepare this second test in parallel with A's edit, but do not submit it until A explicitly says the final code is saved. After staging, use the MCP collaboration read_messages tool to poll for A's saved-revision notification. Do not call the built-in wait_agent tool: it waits for native subagents and cannot receive A/B collaboration messages. Continue polling read_messages until A replies; do not conclude the task at this intermediate stage. The live page loads the latest saved server code on the next filter submission; do not reload the page. After A's final message, click Apply filters for NW-2402 with Processing and report the actual result. It should show no orders. Do not end your turn until that final browser submission is done, unless the desktop-call budget is exhausted. Do not edit files or use Terminal or scripts. Do not treat A's message as proof that the browser is fixed."""

SINGLE_AGENT_INSTRUCTION = """You are S, responsible for both GUI code repair and browser QA. Fix filtering.py so text and status combine conjunctively, then verify Dana plus Processing by pressing Enter in the search field and NW-2402 plus Processing by clicking Apply filters in the visible browser. Save the source change and preserve other files. Use the GUI editor and browser, not Terminal or scripts."""

PUBLIC_REQUIREMENTS = """# OrderDesk filter repair requirements

The local synthetic OrderDesk project has a pre-existing order list and filter controls. The only repair target is filtering.py. Search matches order ID, customer or region after trimming and case folding. A selected status must also match, including when search is nonempty. `All` means no status restriction. In the browser, Dana plus Processing should show only NW-2403 when submitted by Enter in the search field, while NW-2402 plus Processing should show no rows when submitted by the Apply filters button. Apply and Enter share a submit path. Keep the fixture, page, JavaScript, requirements and public test plan intact.
"""
