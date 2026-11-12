# ROUTE-LIVE1 (K2 replacement candidate) — feasibility-stage spec

## Two independent goals
A prepares a Friday Draft route from the released WO-501/502/503/504 manifest, including every order still Scheduled at save time in exact manifest order. B records Riverside Hall's legitimate deferral of WO-503 to Nov. 14 with the caller's exact note. A may not change work orders; B may not edit the route.

Both goals can pass in a shared Guest: after B defers WO-503, A refreshes the board and saves WO-501/502/504. In MA-ID, A's distinct Guest still has all four Scheduled and routes all four while B's distinct Guest defers WO-503. The oracle does not hard-code four stops; it derives the required route from final job statuses.

## Observable contention mechanism
The dispatch route is a derived artifact. If A saves the four-stop route before B's job-status change, the route becomes stale; if A refreshes/rebuilds after B's change, both can pass. Shared+Lock serializes each GUI mutation and screenshot but does not make the multi-step route-building workflow transactional or automatically refresh its application state.

## Hard validation gate
Do not count this as a case yet. First run static oracle controls and live scripted Guest controls for:
1. independent A(4 stops) and B(defer) PASS;
2. shared B-then-A (3 stops + defer) joint PASS;
3. shared A-then-B (stale 4-stop route + defer) A FAIL/B PASS;
4. identical exact fixture reset, DB path and evaluator module parity in all arms.
Then run one GPT-6-Sol MA-ID. Only if both actors exact PASS run matched Shared and Shared+Lock. Preserve recovery: an A refresh/rebuild that restores the current route counts as PASS with recovery cost, not FAIL.
