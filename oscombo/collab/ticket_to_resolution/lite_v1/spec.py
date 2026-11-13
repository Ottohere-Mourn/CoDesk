"""Public task instructions and budgets for Ticket-to-Resolution Lite v1.2."""

from __future__ import annotations

from . import CASE_ID, CASE_VERSION, SOURCE_CASE_ID

CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
ROLE_BUDGET = {
    "A": {"steps": 15, "wall_seconds": 900},
    "B": {"steps": 15, "wall_seconds": 900},
    "S": {"steps": 20, "wall_seconds": 1200},
}

ACTOR_A_INSTRUCTION = """You are the Order Verifier for ticket T-1042. The Case Desk Lite page is open and signed in as A. Compare the customer's report with the order lines, delivery evidence, and return policy shown on the page. Record eligibility, the affected line and evidence, shipping treatment, and the total proposed refund in the review form. Save the review. Its saved-review page displays a real Review ID. Send B a collaboration message saying the review is ready and include that exact ID, but do not include your proposed refund amount. Do not issue a refund or resolve the ticket. Use only the visible GUI and collaboration tools."""

ACTOR_B_INSTRUCTION = """You are the Support Processor for ticket T-1042. The Case Desk Lite page is open and signed in as B. First, before reading A's messages or opening any Case Review, independently compare the customer's report with the visible order lines, delivery evidence, and policy. Complete and save your own pre-verification on your page: eligibility, affected line, supporting evidence, shipping treatment, and proposed total. This is an independent double-check, not a copy of A's answer. After saving it, read A's collaboration message and enter the exact Review ID from that message into the Review lookup in your GUI. Do not use an ID from another source. Compare A's review with your saved pre-verification and source records. If the review is not available, read the collaboration inbox once, then end this turn with a short waiting reply; the runner will resume you when A's review and handoff are available. Do not repeatedly poll. If the review is unclear or differs from your check, ask A for clarification. Once consistent, issue the matching refund and resolve the ticket against the successful transaction. On the resolution form, select "Partial refund - damaged item", enter a brief customer-facing explanation in "Customer resolution note", and click "Resolve Ticket". The note is text, not a currency field: do not enter the refund amount there. Do not alter unrelated records. Use only the visible GUI and collaboration tools."""

SINGLE_AGENT_INSTRUCTION = """Complete the entire T-1042 workflow in the Case Desk Lite GUI. Compare the customer's report with the order lines, delivery evidence, and return policy; save the review and open the saved review to verify it. Continue to the refund form, choose the matching order line and shipping treatment, enter the matching total, and click "Issue Refund". After the successful transaction is visible, continue to Ticket resolution: select "Partial refund - damaged item" under Resolution code, enter a short customer-facing explanation in "Customer resolution note", then click "Resolve Ticket". The note is text, not a currency field: do not enter the refund amount there. Do not stop after saving the review or issuing the refund; the task is complete only when the ticket visibly shows RESOLVED against the successful refund. Use only the visible GUI. Do not use hidden evaluator state."""
