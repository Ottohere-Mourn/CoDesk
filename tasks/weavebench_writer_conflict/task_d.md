# D — publish one internally consistent final report

Read `/workspace/PROJECT_BRIEF.md`, `contract.json`, and `ACCEPTANCE.md`.
You integrate the current shared `/workspace/report.odt`; do not replace it with
an earlier private copy. A/B/C are editing the same document, not producing
independent files for you to concatenate.

Create exactly one **native, outline-generated table of contents**, titled
`Contents`, at the beginning. It must contain all 15 final section titles, their
native chapter numbers 1–15, and correct page references. The full TOC must fit
on page 1; start the body on page 2. Do not type a static imitation of a TOC.

Before final publication, independently check the committed shared requirements:
15 real Heading 1 paragraphs, B's revised titles/numbering, C's typography/page
style/footer and exact limitations note. Handoff files are hints, not proof.
Refresh the actual TOC and relevant document fields after the final changes.

Save the canonical document and export `/workspace/results/report.pdf` from that
same final version. Then write `/workspace/results/publication.json` containing
`odt_sha256` for `/workspace/report.odt`, `pdf_sha256` for that PDF, and `section_ids`
in the prescribed order. A hash receipt alone does not establish correctness:
the evaluator independently re-renders the final ODT and checks PDF content/layout.

If the source changes after export, revalidate, refresh and republish. Do not
publish a stale PDF with a newly copied source hash. Leave the live Writer model
consistent with the saved canonical file, and write `handoff/d.json` when done.
