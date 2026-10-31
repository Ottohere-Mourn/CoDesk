"""Public task instructions and budgets for Ticket-to-Resolution Lite v1."""

from __future__ import annotations

from . import CASE_ID, CASE_VERSION, SOURCE_CASE_ID

CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
ROLE_BUDGET = {
    "A": {"steps": 15, "wall_seconds": 900},
    "B": {"steps": 15, "wall_seconds": 900},
    "S": {"steps": 20, "wall_seconds": 1200},
}

ACTOR_A_INSTRUCTION = """You are the Order Verifier for ticket T-1042. The Case Desk Lite page is open and signed in as A. Compare the customer's report with the order lines, delivery evidence, and return policy shown on the page. Record whether the item is eligible, the affected line and evidence, the shipping treatment, and the total proposed refund. Save the review, then message B that the saved review is ready to inspect; identify the review but do not include your amount in the message. Do not issue a refund or resolve the ticket. Use only the visible GUI and collaboration tools."""

ACTOR_B_INSTRUCTION = """You are the Support Processor for ticket T-1042. The Case Desk Lite page is open and signed in as B. Read A's message and inspect the saved review and source records in the GUI. Independently verify the eligibility, affected line, evidence, policy, shipping treatment, and proposed total. If the review is not yet saved, read the collaboration inbox once, then end this turn with a short waiting reply; the runner will resume you when A's review and handoff are available. Do not spend desktop calls repeatedly scrolling or polling while waiting. If the review is unclear, ask A for clarification. Once it is consistent, issue the matching refund and resolve the ticket against the successful transaction. On the resolution form, select the visible radio option “Partial refund — damaged item”, enter a short customer-facing explanation in “Customer resolution note” (for example: “Approved a partial refund for the damaged USB-C dock.”), and click “Resolve Ticket”. The note is text, not a currency field: do not enter the refund amount there. Do not alter unrelated records. Use only the visible GUI and collaboration tools."""

SINGLE_AGENT_INSTRUCTION = """Complete the entire T-1042 workflow in the Case Desk Lite GUI. Compare the customer's report with the order lines, delivery evidence, and return policy; save the review and open the saved review to verify it. Continue to the refund form, choose the matching order line and shipping treatment, enter the matching total, and click “Issue Refund”. After the successful transaction is visible, continue to Ticket resolution: select the visible radio option “Partial refund — damaged item” under Resolution code, enter a short customer-facing explanation in “Customer resolution note” (for example: “Approved a partial refund for the damaged USB-C dock.”), then click “Resolve Ticket”. The note is text, not a currency field: do not enter the refund amount there. Do not stop after saving the review or issuing the refund; the task is complete only when the ticket visibly shows RESOLVED against the successful refund. Use only the visible GUI. Do not use hidden evaluator state."""
