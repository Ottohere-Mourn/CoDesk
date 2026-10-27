"""Public contract for CDD-LITE-001 v1. No answers or hidden evaluator data."""
CASE_ID = "CDD-LITE-001"
CASE_VERSION = "1.0.0"
CONDITIONS = ("collaborative_shared", "collaborative_isolated")
OUTPUTS = {"A": "outputs/agent_A/verified_analysis.ods",
           "B": "outputs/agent_B/final_management_brief.odp"}
FIXTURE_NAMES = {"authority": "quarterly_authority.ods",
                 "draft": "management_draft.odp", "brief": "case_brief.md"}
ROLE_BUDGET = {"A": {"steps": 40, "model_tokens": None},
               "B": {"steps": 40, "model_tokens": None}}
TOTAL_MODEL_TOKEN_BUDGET = None  # API usage is recorded; no strict token cap is implemented.

AGENT_A_INSTRUCTION = """You are the Data Verifier for a one-slide Q3 management review. In Calc, inspect quarterly_authority.ods and edit only your output copy verified_analysis.ods. Preserve its Sales, Costs and KPI_Definitions sheets. Fill the two blank Findings rows: Q3 gross margin as a percent, and West operating-profit change from Q2 to Q3 in USD thousands. In each Evidence cell cite the relevant Sales and Costs cell ranges/addresses that support the calculation. Gross margin is (revenue - COGS)/revenue. Operating profit is revenue - COGS - fulfillment - promotion. The input file and the draft slide are not your deliverables. Save and publish a complete or useful partial analysis revision, then tell the Report Editor what you verified and where the evidence is. You may work while the editor is preparing the slide. Do not claim that the data prove a cause of the West change. Use Calc and the provided collaboration tools; do not use Terminal, scripts, macros, evaluator files or hidden task data to generate the answer."""

AGENT_B_INSTRUCTION = """You are the Report Editor for a one-slide Q3 management review. The public workbook and unfinished Impress draft are available now; you may inspect and prepare the slide while the Data Verifier works. Edit only your output copy final_management_brief.odp. Before your final save, inspect the verifier's latest saved Findings revision through the GUI, or ask for a specific clarification. Correct the slide's Q3 gross margin, West Q2-to-Q3 operating-profit direction and amount, and the promotion/causality statement using that analysis. Keep the correct title. Replace the pending-source footer with verified_analysis.ods and the first 12 hexadecimal characters of the latest saved analysis SHA-256 from list_saved_artifacts. If A publishes a newer revision, check it before finalizing. Save and publish your presentation; a digest alone is not a substitute for reading the findings. Use Impress, Calc read-only for A's output, and the provided collaboration tools. Do not edit A's workbook, use Terminal/scripts/macros, or access evaluator/hidden data."""
