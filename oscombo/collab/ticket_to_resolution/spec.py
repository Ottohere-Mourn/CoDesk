"""Fixed, synthetic task data and public Actor instructions."""
from __future__ import annotations

CASE_ID = "CDD-TTR-001"
CASE_VERSION = "0.1.0"
TICKET_ID = "T-1042"
ORDER_ID = "O-2048"
CUSTOMER_ID = "C-551"
POLICY_ID = "POLICY-RET-4"
TARGET_LINE_ID = "O-2048-L2"
TARGET_EVIDENCE_ID = "DELIVERY-EV-77"
TARGET_REVIEW_AMOUNT_CENTS = 8_800
TARGET_PRINCIPAL_CENTS = 8_000
TARGET_TAX_CENTS = 800
NONREFUNDABLE_SHIPPING_CENTS = 1_500
ORDER_TOTAL_CENTS = 23_500
POST_REFUND_BALANCE_CENTS = 14_700
EXPECTED_RESOLUTION_CODE = "PARTIAL_REFUND_DAMAGED_ITEM"
IDEMPOTENCY_KEY = "T-1042-REFUND-01"
FIXTURE_DB = "case.sqlite3"

ACTOR_A_INSTRUCTION = """You are the Order Verifier for ticket T-1042. The linked order, item-level delivery evidence, customer message, and refund policy are all available to you; no source facts are hidden. Inspect them and save a Case Review in the application. Record the ticket and order, eligible order line, evidence ID, policy ID, item amount, line tax, proposed refund amount, shipping treatment, and a concise rationale. Do not issue a refund or resolve the ticket. If any source record is unclear or inconsistent, ask the Support Processor a specific question through the message interface and revise your review if needed. Confirm that your saved review can be reopened."""

ACTOR_B_INSTRUCTION = """You are the Support Processor for ticket T-1042. You can inspect the same ticket, order lines, delivery evidence, and refund policy as the verifier. Resolve the case in the support application: check the saved Case Review against the source records, issue the permitted item-level refund referencing that review, and update the ticket with the correct resolution and transaction ID. Do not alter the unaffected monitor, shipping, or unrelated records. If the review conflicts with the source facts or you need clarification, ask the verifier through the message interface before submitting. After issuing the refund, inspect the transaction and finish ticket resolution. A retry after a successful refund must reuse the existing transaction, not create another refund."""

SINGLE_AGENT_INSTRUCTION = """Complete the whole T-1042 support workflow. Inspect the ticket, order, delivery evidence, and policy; save a traceable Case Review; then use that review to issue the appropriate refund and resolve the ticket. You have the combined responsibilities and budget of the verifier and processor. Preserve all non-target records and verify the final transaction and ticket state. No hidden evaluator state is available."""

CONDITIONS = ("single_agent", "collaborative_isolated", "collaborative_shared")
