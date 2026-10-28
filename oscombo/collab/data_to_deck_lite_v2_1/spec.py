"""Actor-visible case contract. This module has no Gold or evaluator answers."""
CASE_ID = "CDD-LITE-002"
CASE_VERSION = "2.0.1"
CONDITIONS = ("collaborative_shared", "collaborative_isolated")
OUTPUTS = {"A": "outputs/agent_A/verified_analysis.ods",
           "B": "outputs/agent_B/final_management_brief.odp"}
FIXTURE_NAMES = {"authority": "quarterly_authority.ods",
                 "draft": "management_draft.odp", "brief": "case_brief.md"}
ROLE_BUDGET = {"A": {"steps": 25, "model_tokens": None},
               "B": {"steps": 25, "model_tokens": None}}
TOTAL_MODEL_TOKEN_BUDGET = None
# Public role dependency for the optional harness lifecycle. This declares
# only who must hand off to whom; it contains no evaluator answer.
HANDOFF_DEPENDENCIES = {"B": "A"}

AGENT_A_INSTRUCTION = """You are the Data Verifier. Your editable Calc workbook verified_analysis.ods is already open. Work on its single West_Finance sheet. Calculate the change in West operating profit from Q2 to Q3, in USD thousands. Operating profit = Revenue - COGS - Fulfillment - Promotion. Enter the signed change in cell B6 and identify the input cells in D6 (a range such as B3:E4 is sufficient). The two quarter rows are already visible; use the Calc GUI. Save your workbook, then use publish_saved_artifact and send_message to hand the result and its source range to the Report Editor. You can work while B prepares the draft. Edit only your output workbook. Do not use Terminal, scripts, macros, hidden evaluator data or the Gold files to calculate or write the answer."""

AGENT_B_INSTRUCTION = """You are the Report Editor. Your editable one-slide Impress file final_management_brief.odp is already open. The slide has a title and one large unfinished conclusion text box. You may inspect and prepare it while A works. Wait for A's saved workbook revision and message before finalizing. Use A's verified signed West Q3-minus-Q2 operating-profit change to replace the unfinished conclusion with one clear management sentence: state the direction and amount in USD thousands, and cite verified_analysis.ods as the source. If A's message is unclear, ask for clarification. Save your slide and use publish_saved_artifact. Do not finish before A's handoff. Edit only your output presentation. Use the Impress GUI; do not use Terminal, scripts, macros, hidden evaluator data or Gold files to write the answer."""
