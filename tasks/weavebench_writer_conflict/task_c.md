# C — format the same report and add the supplied review note

Read `/workspace/PROJECT_BRIEF.md`, `contract.json`, and `ACCEPTANCE.md`.
Edit the already-open canonical `/workspace/report.odt`.

- Set the shared Heading 1 style to **Liberation Sans, 18 pt, bold, #1F3A5F**.
  Keep headings with the following paragraph. Do not reset its outline/numbering
  properties or overwrite B's wording.
- Set original body paragraphs and the added note to the **Text body** paragraph
  style, Liberation Sans **11 pt**. Preserve their original text/order.
- Use one **A4 portrait** page style, **20 mm** on all four margins. Enable a footer
  containing a real current-page-number field, not a typed literal page number.
- Insert `/workspace/review_note.txt` verbatim, exactly once as a new paragraph
  after the original body of `sec_08` (Limitations) and before `sec_09` (Future Work).

Preserve all section bookmarks, A's heading assignments and B's chapter numbering.
Do not insert hard page breaks between chapters. D may put the first body heading
on a new page after the TOC. Your layout/content changes can invalidate D's page
references and PDF, so announce readiness only after the canonical document is saved.
Write `handoff/c.json`; do not maintain a separately formatted output copy.
