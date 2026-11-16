# A — repair the shared outline without reverting other editors

Read `/workspace/PROJECT_BRIEF.md`, `contract.json`, and `ACCEPTANCE.md`.
Work on the already-open `/workspace/report.odt`, not a private final copy.

Inspect the initial paragraph style and outline level for every `sec_01` through
`sec_15` bookmark. Identify the seven seed sections that are not real Heading 1.
Write their stable IDs to `/workspace/results/structure_audit.json` as
`{"wrong_section_ids": [...], "inspection": "..."}`. The inspection explanation
must describe the actual properties you checked, not merely visual boldness.
Use IDs rather than title strings because B is revising some titles concurrently.

Normalize all 15 section paragraphs to **Heading 1, outline level 1**, retaining
the current title text, their bookmark ranges, section order and original body.
Do not rewrite titles from an old list or reset Heading 1's font/numbering/page
properties: those belong to other editors. Reacquire current ranges if they moved.

Save your changes to the canonical document, verify they remain present, and
write `handoff/a.json` after committing. No separate A-only ODT is accepted.
