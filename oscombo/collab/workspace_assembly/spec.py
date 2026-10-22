"""Task contract for Workspace Assembly V0."""
from __future__ import annotations

from . import CASE_ID, CASE_VERSION, CONDITIONS

REPORT_SOURCE = "incoming/Quarterly_Supply_Report.odt"
REPORT_FINAL = "delivery/Quarterly_Supply_Report.odt"
MANIFEST_FINAL = "delivery/attachment_manifest.csv"

ATTACHMENTS = (
    {"asset_id": "ATT-CHART-01", "source": "incoming/q3_chart_final.png",
     "target": "delivery/attachments/q3_revenue_chart.png", "description": "Q3 revenue chart"},
    {"asset_id": "ATT-TERMS-01", "source": "incoming/vendor_terms_final_v2.pdf",
     "target": "delivery/attachments/vendor_terms.pdf", "description": "Vendor payment and delivery terms"},
    {"asset_id": "ATT-STOCK-01", "source": "incoming/inventory_week42.csv",
     "target": "delivery/attachments/inventory_snapshot.csv", "description": "Week 42 inventory snapshot"},
    {"asset_id": "ATT-COMP-01", "source": "incoming/supplier_compliance_note.txt",
     "target": "delivery/attachments/compliance_summary.txt", "description": "Supplier compliance summary"},
)
PROTECTED_PATHS = ("incoming/README.md", "incoming/Project_Brief.md", "archive/q2_baseline.txt")
REPORT_LINKS = {
    "Q3 revenue chart": "attachments/q3_revenue_chart.png",
    "Vendor terms": "attachments/vendor_terms.pdf",
    "Week 42 inventory snapshot": "attachments/inventory_snapshot.csv",
    "Supplier compliance summary": "attachments/compliance_summary.txt",
}

ACTOR_A_INSTRUCTION = """You are A, the delivery-file coordinator. The incoming project folder contains the full source set and the report draft; no files are hidden. Use the file manager to create the delivery folder, move and rename the four referenced attachments according to the project brief, and produce `delivery/attachment_manifest.csv` with each attachment ID, relative path, SHA-256, and description. Preserve the source bytes exactly and leave unrelated files in place. Verify B's updated report links against the final folder and manifest; if a filename or digest does not match, message B with the concrete discrepancy and reconcile it. You own file organization and the manifest, not the Writer report. Messages and attachments are available when useful; no message count or timing is prescribed."""

ACTOR_B_INSTRUCTION = """You are B, the report editor. Read the complete project folder and brief; all files are visible. Use Writer to move the draft to `delivery/Quarterly_Supply_Report.odt`, preserve its existing report content, and update its four attachment references to the final relative paths listed in the brief/manifest. Keep the reference labels descriptive and ensure every link resolves from the report's delivery directory. Ask A about a missing or ambiguous attachment only if the visible materials do not resolve it. Reopen and verify the saved ODT after A's path changes. You own the report, not the attachment renames or manifest. Messages and attachments are available when useful; there is no prescribed number or timing."""

SINGLE_AGENT_INSTRUCTION = """Prepare the Project Aurora delivery package. Use the file manager to organize and rename the four listed attachments into `delivery/attachments/`, preserve their bytes, and create `delivery/attachment_manifest.csv`. In Writer, move the existing report into `delivery/`, preserve its content, and update all four relative attachment links to the final paths. Verify hashes, links, and protected files. All source materials are visible; no hidden evaluator state is available."""

BRIEF = """Project Aurora handoff: prepare a clean delivery folder from the supplied partial project directory. Move and rename the four attachments using the final names shown in the public asset brief, preserve each file byte-for-byte, and create a manifest with IDs, relative paths, SHA-256 digests, and descriptions. Move the existing ODT report into `delivery/`, preserve its narrative, and update its attachment references so each path resolves from the report location. Keep `incoming/README.md` and `archive/q2_baseline.txt` unchanged. The A/B roles own the file organization/manifest and Writer report respectively; both can inspect all materials and use the shared message/attachment API. Shared desktop events and filesystem/version changes must be recorded separately. No simultaneous GUI action is required."""

PUBLIC_ASSET_BRIEF = """# Project Aurora asset handoff

Prepare these four source files for delivery. Preserve file bytes exactly.

| ID | Source | Final path | Description |
|---|---|---|---|
| ATT-CHART-01 | `incoming/q3_chart_final.png` | `delivery/attachments/q3_revenue_chart.png` | Q3 revenue chart |
| ATT-TERMS-01 | `incoming/vendor_terms_final_v2.pdf` | `delivery/attachments/vendor_terms.pdf` | Vendor payment and delivery terms |
| ATT-STOCK-01 | `incoming/inventory_week42.csv` | `delivery/attachments/inventory_snapshot.csv` | Week 42 inventory snapshot |
| ATT-COMP-01 | `incoming/supplier_compliance_note.txt` | `delivery/attachments/compliance_summary.txt` | Supplier compliance summary |

The report will live at `delivery/Quarterly_Supply_Report.odt`; its links must be relative to that directory (for example, `attachments/vendor_terms.pdf`). Keep `incoming/README.md` and `archive/q2_baseline.txt` unchanged.
"""

CONDITION_RULES = {
    "backend": "one canonical run-scoped project workspace and identical initial tree in all conditions",
    "isolated": "two independent desktop sessions, each connected to the same canonical workspace backend; separate GUI navigation/focus state",
    "shared": "one live desktop session and the same canonical workspace backend; shared GUI navigation/focus state",
    "messages": "existing Data-to-Deck ProtocolStore API with identical A/B capabilities in every condition",
    "file_changes_are_not_gui_interference": True,
}

ROLE_BUDGET = {"steps": 240, "model_tokens": 12000, "calibrated": False}
