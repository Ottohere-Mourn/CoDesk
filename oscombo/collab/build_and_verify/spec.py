"""Public task contract and deterministic acceptance fixture."""
from __future__ import annotations

CASE_ID = "CDD-BV-001"
CASE_VERSION = "0.1.0"
CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
DATA_FILE = "data/orders.json"
FILTER_FILE = "filtering.py"
APP_FILE = "static/app.js"
PROTECTED_FILES = (
    "README.md", "requirements.md", "data/orders.json", "static/index.html",
    "static/style.css", "tests/public_test_plan.json",
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
    {"query": "no-such-order", "status": "All", "ids": ()},
)

ACTOR_A_INSTRUCTION = """You are A, the OrderDesk developer. Repair the existing order-list filter in the supplied project. Search text and selected status must combine conjunctively; search is trimmed and case-insensitive across order ID, customer, and region. Applying with the visible button or Enter must use the same filters without navigating away. Keep the provided data, page structure, and unrelated files intact. You can read the task requirements and test plan, and can inspect the running application. B is responsible for browser validation and may send concrete observations or a regression request. Make a focused change, then tell B what changed when useful. Do not edit the fixture or the evaluator."""

ACTOR_B_INSTRUCTION = """You are B, the browser QA analyst. Use the visible OrderDesk browser interface to test the order filters against the requirements and public test plan. You may inspect the same source and data as A. Check status-only, combined search+status, case/whitespace handling, no matches, and keyboard submission with Enter as well as the Apply button. Report reproducible observations and any regression to A through the shared message/attachment interface; after a code change, rerun relevant browser checks and report whether they pass. Do not edit application source or fixture data. Do not infer a pass from a success banner alone: compare the rows shown with the visible records and requirements."""

SINGLE_AGENT_INSTRUCTION = """You are S, responsible for both development and browser QA. Repair the order filters so text and status combine, search is trimmed/case-insensitive, and both Enter and Apply work without page navigation. Inspect the supplied source/data, implement a focused fix, run the public test plan through the app, and preserve all non-target files. No hidden evaluator state is available."""

PUBLIC_REQUIREMENTS = """# OrderDesk filter repair requirements

The local synthetic OrderDesk project has a pre-existing order list and filter controls. Keep the fixture and page layout. The text field searches order ID, customer name, and region; matching is trimmed, case-insensitive substring matching. The status selector and text query are conjunctive when both are set. `All` means no status restriction. An empty result must be announced in the result status region. Submitting with Enter and activating Apply must produce the same filtered list without a document navigation. Clear resets both controls and returns all rows. Do not alter totals, statuses, customer/order data, styles, requirements, or public test plan.
"""
