# Collaborative Interdependence Topologies & Anti-Patterns

Read this reference when designing interdependence structures or auditing why a collaborative case is too trivial, deadlocked, or leaky.

## 1. Three Authentic Interdependence Topologies (Where Solo Execution Truly Cannot Succeed)

### Topology A: Bidirectional Constraint Negotiation (Cross-Domain Design Loop)
- **Structure**: Role A owns private domain-A measurements/CAD/UI (`ws_a` + live GUI app A) that determine feasible curve `f(x)`, while Role B owns private domain-B measurements/telemetry/localization (`ws_b` + live GUI app B) that determine feasible curve `g(y)`. Choosing a valid joint operating point `(x*, y*)` in the shared artifact/GUI requires **combining derived facts from both domains**.
- **Example**: In a rail/medical HMI release (`Qt5 Designer` + `Qt5 Linguist` + `Calc`), Role A computes minimum physical gauge & button geometry from braking/ergonomic test logs, while Role B translates approved regulatory strings whose rendered pixel widths constrain banner layout—neither knows the feasible pixel split until both exchange their derived bounds and co-verify the live `.ui` + `.qm` build.

### Topology B: Cross-Role Investigative Handoff + Joint Synthesis
- **Structure**: Role A extracts reconciled entity/clinical/GIS anomalies from raw source set A, which filters or re-weights Role B's downstream model/simulation, AND Role B's resulting tax/thermal/hydraulic output feeds back into Role A's final executive/CAD sign-off.
- **Why it is fair here (unlike `SA-01` / `SD-01`)**: In `SA-01`, Role A was *never told* Role B existed and was locked out after its first close. Here, **both prompts explicitly name the partner and the two-way dependency**, and edits remain open until both roles finish.

### Topology C: Shared Monolithic Artifact Co-Authoring + Pre-Exit Joint Verification
- **Structure**: Two specialists co-author a live multi-track `Blender VSE` cut, multi-solid `FreeCAD .FCStd` assembly, multi-layer `QGIS` geodatabase, or `LibreOffice Calc + Writer` closing pack where global totals/clearances/cross-references span both sections.
- **Natural Failure Mode on `shared_desktop`**: Even when agents write handoff notes in `/workspace/shared_project`, sharing **one `:99` display** creates real GUI friction: singleton `soffice.bin` / `GIMP` / `Blender` dirty-buffer overwrites, modal dialog preemption (`Scale Image`, `Export`, `Find & Replace`), global XKB layout switches (`DE-QWERTZ`), or premature exit by the faster agent before verifying that the slower partner's final GUI save preserved joint invariants.

---

## 2. Collaborative Anti-Patterns to Reject

1. **Disguised Independent Tasks (`Gate 2` Violation)**
   - Giving Role A and Role B two unrelated sub-problems whose answers are merely pasted into two separate JSON files (or fake `[a_min, a_max] + [b_min, b_max] == [c_min, c_max]` decoupled intervals).
2. **Scripted Synchronization Choreography in `task.md`**
   - Writing *"Write your numbers to `/workspace/shared/handoff.json`, poll every 5s until `b_done == true`, acquire `flock /tmp/gui.lock` before clicking Calc"*. State **what** the team must deliver and **who** the partner is—never script the locking/polling algorithm.
3. **First-Submission Silent Locks & Artificial Write-Bans**
   - Locking grading on the first draft (`official_wire_receipt`) so an agent cannot update its work after receiving its partner's numbers, or banning writes for 25 minutes.
4. **Tight Timeouts (`< 7200s`) & Step Caps (`max_cua_calls`)**
   - Collaborative negotiation + GUI recovery naturally takes longer than solo work. Cutting off agents at `1080s-1500s` or `140` CUA calls measures clock truncation instead of collaboration quality.
5. **Asymmetric Scoring Multipliers (`j_mult`) & Brittle Format Regexes**
   - Applying a `shared_desktop`-only `0.75` multiplier, or parsing `.ui`/`.xlsx`/`.odt`/`.FCStd` with fragile string checks instead of real libraries (`PyQt5.uic.loadUi`, `LibreOffice`, `FreeCAD`, `QGIS`, `Blender`).
