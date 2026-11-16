# Riverton evacuation-access release

Prepare the evacuation-access portion of the supplied synthetic municipal review
in the existing live `RivertonReview.qgz` and shared `review.gpkg`.
GUI, CLI, Python and application APIs are allowed. Only `access_*` derived tables,
the `Access_Review` group/layout and your `exports/access/` files are yours.
Preserve unowned content and source tables. Short file/database locks and bounded
retries are allowed; a stale whole-project or whole-database replacement is not.

## Access analysis

- Read the supplied directed road graph, travel times, fixed closure list,
  accessibility flags, origin demands and shelter capacities. These inputs are
  authoritative; no unfinished exposure-analysis output is needed for this task.
- Compute admissible origin-to-shelter paths respecting direction, closures and
  accessibility eligibility. A straight line or undirected shortest path is not
  an acceptable substitute. Explain isolated or ineligible origins explicitly.
- Allocate integer persons; splitting an origin across shelters is allowed.
  First minimize unserved demand, then minimize total person-minutes among those
  allocations. Your cost may be at most 1% above the optimal feasible cost under
  `access_policy.json`. Never exceed shelter capacity or count one person twice.
  Different routes or allocations with equivalent feasible cost are acceptable.
- Record origin, shelter, allocated persons, ordered edge IDs, travel time and
  unserved reason where applicable. Reconcile every origin and shelter total.

## Native review and release

Create editable route and exception layers in the existing project. Your A4
`Access_Review` layout must distinguish served routes, fixed closures and unmet
demand without hiding them under the basemap. Include an allocation summary,
travel-time units, a readable legend and the review date. Do not modify or remove
other project groups, layout definitions or GeoPackage tables.

Publish `exports/access/access_routes.gpkg`, `allocation.csv` and
`access_review.pdf`. Exports must agree with your committed native data and use
portable relative project sources.

In the real QGIS application, review a capacity-limited origin's table entries
and highlighted route, then an unreachable origin and its closure context.
Use normal desktop observations to inspect linked selection and the saved layout;
a generated picture is not evidence of a live selection. These are time-local
review checkpoints, not a requirement to retain the active window afterward.

Reopen your release and check consistency. Do not solve this task by changing
capacities, closures or baseline demand. This is a synthetic planning exercise,
not a real emergency-routing recommendation.
