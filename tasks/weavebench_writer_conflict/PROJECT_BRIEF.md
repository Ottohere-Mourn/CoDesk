# One report, four concurrent editors

This is a derived task seeded from WeaveBench's heading-style normalization
document. It is not four independent documents and is not an official WeaveBench
leaderboard task. Read `contract.json` and `ACCEPTANCE.md` before editing.

## Shared state

All four agents edit the **same already-open `/workspace/report.odt` in one
LibreOffice Writer session**, on one desktop. `/tmp_workspace` aliases
`/workspace`. The existing paragraphs contain 15 stable bookmark ranges named
`sec_01` through `sec_15`; their original and required final titles are in the
contract. The initial visible text and seven heading-style errors are retained
from the seed. Original section order must remain unchanged.

There is exactly one authoritative document. Per-agent copies are not separate
deliverables. Temporary copies/CLI processing are allowed, but any patches must
be merged into the latest canonical document and reflected in the live Writer
model, without losing other editors' updates. A whole-file overwrite based on
an old snapshot is not a valid merge. Do not kill or replace the shared application
session to discard other editors' in-memory work. Finish by explicitly saving;
the evaluator will not save, refresh fields or merge files on your behalf.

GUI, shell, Python, UNO, and XML inspection/editing are allowed. There is no hidden
method ban and no harness-provided input mutex. Short critical sections and
coordination through the normal shared filesystem are allowed and will be
measured, not supplied automatically. There is no separate agent chat tool.
Robust concurrency control is a valid solution, not a reason to lower the score.

## Ownership and dependencies

| Role | Own changes | Shared dependencies |
|---|---|---|
| A | Paragraph heading structure and initial-style audit | Preserve B's current title text and C's typography |
| B | Three title revisions and native chapter-numbering rules | Applies to the same paragraphs/Heading 1 style normalized by A |
| C | Heading/body/page typography, footer, limitations note | Preserve structure, bookmarks, numbering and title revisions |
| D | Generated TOC, final PDF and version-bound publication receipt | Must reflect the committed A/B/C results, not an earlier version |

Do your assigned changes; do not silently take over another role's assignment.
Do not delete or reset shared styles/documents wholesale. Preserve all original
body paragraphs and their order; C's supplied note and D's TOC are the only
authorized new content. Preserve all stable bookmarks. A must inspect and record
the initial mis-styled section IDs before fixing them; the other roles must not
change the heading assignments owned by A.

After saving your owned changes, write `handoff/<role>.json` with your role,
`ready: true`, and a brief note. If you change the document again, mark yourself
not ready first. These are coordination hints, not trusted evidence or grades.
Their individual file hashes need not equal the final hash after other editors'
changes. D must independently recheck the final shared contract before publishing.

The final PDF is an integration deliverable: an upstream failure can block D.
Assessment reports owned checks, dependencies and joint consistency separately;
it does not pretend all four roles are independent success trials.

## Evidence and boundaries

The broker records real screenshots/actions. Optional screenshots may be saved
under role-specific filenames for human review, but image existence alone is not
treated as proof of authenticity or success. Never fabricate evidence. No private
display server, GUI profile, hidden reference answer or grader access is allowed.

The controller observes saved document versions and captures the live model after
all agents stop. Observations do not repair, reformat, refocus or update the
document during execution. Intermediate files that were correct and later became
incorrect are reported as possible lost updates, not silently replaced by the
best earlier snapshot. Final publication must match the final committed version.
