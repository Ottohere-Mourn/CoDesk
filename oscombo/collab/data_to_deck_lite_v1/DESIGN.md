# Data-to-Deck Lite v1 — frozen design before implementation

Case ID `CDD-LITE-001`, version `1.0.0`. This is a new case; the original `CDD-RECON-001` task, fixture, Gold, Oracle and runs remain unchanged.

## User need and shortest collaboration chain

A manager needs a one-slide Q3 review. The shared raw workbook contains Q2/Q3 regional Sales and Costs, but the draft slide carries three errors. Agent A verifies the Q3 gross-margin percentage and West Q2→Q3 operating-profit change in Calc and records traceable source cells. Agent B may inspect and prepare the draft at the same time. B must then use A's saved analysis revision to finish the slide: correct gross margin, correct the direction and magnitude of the West change, and distinguish a simultaneous promotion increase from proven causation. B cites the actual analysis artifact's SHA-256 prefix. A can publish a preliminary saved revision; no fixed handoff instant or forced concurrent click is prescribed.

Both roles receive the same public workbook and draft in both topology conditions. That keeps original information and saved-file visibility equivalent. The raw data are also available to B, so B could independently recompute them; the benchmark tests actual use of A's published revision through version, message and GUI traces rather than pretending A has exclusive knowledge. B's success depends on the final A artifact's values and digest. A valid digest string alone is insufficient evidence of behavioral collaboration.

## Public fixture and workspace

- `quarterly_authority.ods`: Sales (six Q2/Q3 regional rows), Costs (matching six rows with COGS, fulfillment and promotion), KPI_Definitions, Findings. Findings preprints two metric labels and units only; answer and evidence cells start blank. Raw source sheets are read-only input and copied to A's editable deliverable.
- `management_draft.odp`: one slide with a title, three incorrect or incomplete statements, and a pending-source footer. It is copied to B's editable deliverable.
- `case_brief.md`: task context, metric definitions, roles, output paths, and rules. It gives no computed values.
- The same original public files are installed in both conditions. In isolated mode the existing saved-artifact bridge mirrors only complete output ODF files, keeps immutable revisions, records ownership, and verifies peer bytes. Shared mode uses one desktop with no keyboard/mouse lock.

Guest paths stay `/tmp/codesk-data-to-deck-lite-v1/input` and `.../outputs/agent_A/verified_analysis.ods`, `.../outputs/agent_B/final_management_brief.odp`. Each run has its own host run_id, Guest overlay and logs.

## Role goals and independent scoring

A fills exactly two Findings values in the output workbook: Q3 gross margin in percent and West operating-profit change in USD thousands. Evidence must identify the relevant raw Sales and Costs cell ranges for each calculation; numerical correctness plus a nonempty generic Evidence string is not enough. Protected source sheets and declared units must remain correct.

B produces exactly one slide. Its text must express the correct Q3 gross margin, the West operating-profit decline and its size, the West promotion increase, and the limit of causal inference. Equivalent numeric formatting and ordinary English paraphrases are accepted. The slide must preserve the correct title and contain an actual short digest of A's *final saved* workbook. B may start before A finishes; the final save must use the latest valid revision.

The Oracle runs on collected ODF bytes outside the Actor environment. It independently reads source values, checks A's results and source references, verifies B's values/direction/causal boundary and checks the deck citation against A's final file hash. It reports A, B, joint and protection checks separately. A separate trace audit checks whether B read a delivered revision or corresponding message/attachment and whether the read preceded the final deck save. The Oracle cannot infer behavioral collaboration from a digest alone.

## Positive/negative controls and fairness gates

Positive controls generate correct ODS/ODP only on the scoring side and include a real-GUI scripted variant. Negative controls include wrong value, swapped gross/operating margin, evidence that names unrelated cells, correct value with a fabricated digest, stale digest after A resave, incorrect West direction, unsupported causal claim, protected-input modification and malformed/partial ODF. Actual Guest Smoke must show Calc/Impress launch, GUI input, save, collection, same-byte reopen, Oracle, workspace propagation and clean reset in both topologies.

For model comparison use identical `gpt-6-astra`, role prompts, fixture bytes, tool surface, per-role 40 GUI tool calls and 1200-second actor timeout in both conditions. This is a ceiling, not a target; expected useful work is roughly 15–30 calls per role and must be measured. Model tokens and API latency are recorded from usage events. The current remote harness does not implement an exact total-token hard cap, so no such cap will be claimed. Two model processes start behind a barrier and execute concurrently. Only a short compatibility probe, one small pilot, and one full Shared plus one full Isolated run are authorized for this version. Keep all failures and do not tune against a condition's score.
