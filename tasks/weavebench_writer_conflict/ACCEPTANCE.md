# Public acceptance contract

All requirements used for grading are visible here and in the role prompts.
This derived workload uses deterministic checks, not the original task's hidden
UNO/XML prohibition or ad-hoc LLM caps. Role checks and joint checks are separate.

## Owned checks

- A: all 15 stable section bookmarks survive in original order; every bookmarked
  paragraph is Heading 1 at outline level 1; the initial seven wrong section IDs
  and a nonempty actual-property inspection explanation are recorded accurately.
- B: all titles match `contract.json` (three revised, the rest preserved); the
  level-one chapter-numbering definition uses Heading 1, Arabic integers starting
  at 1 and suffix `. `. Numbers are not manually prepended to title text.
- C: Heading 1 and Text body have the specified typography, A4 portrait and 20 mm
  margins are configured, an actual footer page-number field exists, and the
  exact supplied note appears once inside the Limitations section. Original body
  paragraphs remain in their sections and order.
  Page dimensions/margins allow 0.02 mm native unit-rounding tolerance. Empty
  spacer paragraphs may be reused; nonempty original body text must be unchanged.
- D: one real generated TOC exists; its 15 cached entries match the final numbered
  titles and actual PDF section pages; TOC on page 1, body beginning on page 2;
  PDF and a correct source/PDF SHA-256 receipt exist.

## Joint consistency

- The saved file and the authoritative live Writer document agree on section
  titles, heading assignments and numbering. The live document has no unsaved changes.
- A/B/C's owned edits coexist, not merely in different temporary files or past
  versions. No stale whole-document save may erase an earlier editor's work.
- The submitted PDF matches an independent native re-export of the final ODT:
  per-page extracted text, page count/size and rendered page pixels are checked.
  The grader re-exports to a private evaluation directory, never repairs/saves
  the submitted ODT. SHA-256 receipts are checked but never trusted alone.
- For native re-render comparison, corresponding page images are compared at
  72 DPI, RGB: mean absolute channel difference ≤ 0.1/255 and fraction of pixels
  with any channel difference > 8 ≤ 0.001. This tolerance only covers rendering
  noise; structural and text requirements remain exact.

Each owned check is binary and contributes equally within its role. Joint success
requires every owned and joint check. Publish the check vector as well as any
aggregate; do not hide upstream/dependency failures behind a single average.
Authenticity review uses recorded trajectories; valid PNG dimensions alone are
not proof that evidence is genuine. API failures, application errors and dependency
failures must remain distinguishable from measured concurrent-state conflicts.
