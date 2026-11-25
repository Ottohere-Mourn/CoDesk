# Work Order — Execution Implementation Shortfall & Responsive Order-Drawer QA (`execution_quant_researcher`)

## Context & Objective
Audit European equity child-order execution quality, parent limit-collar compliance, and responsive UI behavior on the Trading Data Portal (`http://127.0.0.1:19505/quant-workbench` in Chromium). Read ``/workspace/docs/Execution_Microstructure_SOP.pdf`` and reconcile ``/workspace/tapes/parent_orders.csv`` with ``/workspace/tapes/child_executions.csv`` against the live production corporate-action ex-date & tiered venue fee schedules.

## Deliverables
- Write ``/workspace/execution_qa_audit.json`` conforming to Section 4 of ``Execution_Microstructure_SOP.pdf``, covering cleaned continuous-trading execution shortfall metrics, venue rankings, taker adverse-selection markouts, the structural slippage break day, and the responsive layout/modal defects observed on `/quant-workbench`.
