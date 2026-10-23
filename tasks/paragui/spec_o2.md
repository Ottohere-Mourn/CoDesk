# Pair o2 - one Writer contract: resolving tracked changes vs. inserting a data-protection clause

Family F1 (office documents). Tasks `pgo2redlines` (A) and `pgo2dpa` (B). Files: `build_o2.py`, `pg_o2.py`
(helpers `pg_olib.py`, scans `lib_oscan.py`), `task_pgo2redlines.py`, `task_pgo2dpa.py`.

## Scenario and persona

Legal operations at Corvid Analytics Ltd (a UK data-analytics supplier) is finalising a Master Services Agreement with
the client Brightline Retail plc. `~/Documents/Contracts/Brightline_MSA_v4.docx` (A4, ~5 pages, title page with a real
table-of-contents field, 12 clauses with manual numbers "N." in Heading 1 paragraphs and "N.M" sub-clauses, 12
cross-references "Clause N(.M)") came back with **18 tracked revisions from three reviewers** (Priya Raman - our
counsel; Daniel Okafor - Brightline procurement; Marta Lindqvist - our finance) and **3 review comments**.
Track-changes recording is off.

- **A**: the head of legal (email `Email_from_Hannah.txt`) wants every reviewer change resolved: accept Priya's,
  follow her handwritten call notes (`call_notes_2026-10-14.pdf`, image-only) for Daniel's and Marta's, and for points
  the notes do not cover reject Daniel's / accept Marta's; delete the comments; list the rejected Brightline points.
- **B**: Brightline's DPO signed off a data-protection rider (`Rider_DP-1_Data_Protection.pdf`, 2-page scan): insert it
  as new Clause 8, add a definition, renumber clauses 8-12 -> 9-13 with their sub-clauses and every cross-reference,
  add clause 8 to the survival list, update the TOC, save, export a PDF for the DPO.

Provenance: redlining an MSA round with several reviewers and a "call notes decide" rule, and inserting an agreed
rider with renumbering + TOC refresh, are daily paralegal/contract-manager work (cf. common "accept changes by one
reviewer only", "renumber clauses and cross references", "update table of contents" questions on the Word/Writer
help forums and Ask LibreOffice).

## Requests (verbatim)

**A - pgo2redlines**
> I work in legal operations at Corvid Analytics. The Brightline master services agreement ~/Documents/Contracts/Brightline_MSA_v4.docx is open in LibreOffice Writer; it came back with tracked changes and comments from three reviewers. Please do what our head of legal, Hannah, asks in ~/Documents/Contracts/Email_from_Hannah.txt: resolve every one of the reviewers' tracked changes according to her rules and her scanned call notes (~/Documents/Contracts/call_notes_2026-10-14.pdf), delete the review comments, save the document in place as .docx, and write the list of points where we rejected Brightline's edits to ~/Documents/Contracts/Brightline_rejected_points.txt.

**B - pgo2dpa**
> I work in legal operations at Corvid Analytics. Brightline's data protection officer has signed off the wording of a new data protection clause; it is in the scanned rider ~/Documents/Contracts/Rider_DP-1_Data_Protection.pdf. Please put it into the master services agreement that is open in LibreOffice Writer (~/Documents/Contracts/Brightline_MSA_v4.docx) exactly as the rider instructs: new Clause 8 'Data Protection' right after Clause 7 (Confidentiality) with the same heading style as the other clauses, the new definition in clause 1.1, the following clauses, their sub-clauses and all cross-references renumbered, and the new clause added to the list of clauses that survive termination. Then update the table of contents, save the document in place as .docx, and export a PDF of the updated agreement to ~/Documents/Contracts/Brightline_MSA_DPA_review.pdf for their DPO. Leave the reviewers' tracked changes and comments as they are - a colleague is handling those.

## The 13 tracked changes and their required outcome (A)
| id | reviewer | change | outcome (why) |
|---|---|---|---|
| P1 | Priya | new definition "Business Day" (inserted paragraph) | accept (Priya) |
| P2 | Priya | "use **all** reasonable endeavours" | accept |
| P3 | Priya | delete duplicated sentence in 7.2 | accept |
| P4 | Priya | typo recieving -> receiving | accept |
| D1 | Daniel | payment 30 -> 60 days | reject (notes 1) |
| D2 | Daniel | liability cap 100% -> 200% | reject (notes 3) |
| D3 | Daniel | monthly written service report | accept (notes 4) |
| D4 | Daniel | termination for convenience, 90 days | accept (notes 5) |
| D5 | Daniel | deletes the Supplier pre-existing IP clause 6.2 | reject (notes 6) |
| D6 | Daniel | governing law -> Scotland | reject (not covered -> Daniel default) |
| M1 | Marta | new 4.5 CPI indexation (inserted paragraph) | reject (notes 7) |
| M2 | Marta | late-payment interest 4% over base | accept (notes 2) |
| M3 | Marta | invoicing monthly in arrears -> in advance | accept (not covered -> Marta default) |

## Shared resources
`~/Documents/Contracts/` (docx opened once in Writer, email, two scans). Both tasks edit the same open document.

## Expected contention when run simultaneously
- One Writer window: A works in Edit > Track Changes > Manage (non-modal dialog that selects/jumps to each change,
  moving the shared cursor) while B types the new clause at a cursor position and uses Find & Replace for
  renumbering - each agent's cursor jumps move the other's insertion point; B typing while A's accept/reject
  selection is active replaces text; B's Find & Replace "Replace All" can hit text inside pending changes.
- B must not touch reviewer changes, but an agent that "cleans up" by accepting all changes before exporting the PDF
  destroys A's work (A's checker then sees wrong outcomes).
- Saving: script-based edits of the .docx (python-docx/XML) are overwritten by a later Save from Writer, and vice
  versa; the "Keep current format" dialog appears for whichever agent saves.
- B's TOC/PDF must be produced after B's own renumbering; A's later changes do not invalidate B's PDF (graded only for
  B's content).

## GUI-only parts
- A: the decisions are in a handwritten-style image scan; tracked changes/comments are Writer application state
  (scriptable via XML only with considerable effort).
- B: the clause wording and instructions exist only in the 2-page image scan; TOC refresh and PDF export are Writer
  functions (Tools > Update > Update All, File > Export as PDF).

## Grading (host side; `expected.json`)
Visible text = pending insertions shown, pending deletions hidden. Text checks are on normalised text and never
depend on clause numbers (B renumbers) or on B's additions.

**A - `evaluate_redlines`** (1.0)
- 0.60: 13 changes x (expected text present / alternative absent, and no revision carrying this change's text is
  still pending).
- 0.10: no revision by any of the three reviewers left in the document.
- 0.10: none of the reviewers' comments still anchored in the document.
- 0.20: `Brightline_rejected_points.txt` mentions the four rejected Brightline points (payment 60 days, liability
  200%, pre-existing IP / Supplier Materials, governing law Scotland), 0.05 each.
- Cap: no correct change -> <= 0.2.

**B - `evaluate_dpa`** (1.0)
- 0.10 heading "8. Data Protection" between Confidentiality and Warranties; 0.05 same paragraph style as clause 7.
- 0.15 the five rider paragraphs present in clause 8 (similarity >= 0.9 each, number stripped).
- 0.05 the "Data Protection Legislation" definition inside clause 1 (similarity >= 0.88).
- 0.10 headings 9-13 renumbered (Warranties ... General); 0.10 every sub-clause number in clauses 8-13 matches its
  clause.
- 0.15 13 cross-reference checks: 12 references (including the trap "this Clause 7", which must stay 7) plus the
  survival list = {1, 6, 7, 8, 10, 12}.
- 0.10 the document's TOC lists all 13 new headings.
- 0.20 PDF `Brightline_MSA_DPA_review.pdf`: 0.5 clause 8.3 text found; 0.5 the PDF's own contents page lists the
  13 headings with page numbers that match the pages the headings are on (constant offset tolerated) - i.e. the TOC
  was updated after the edits and before the export.
- Cap: no clause 8 heading -> <= 0.3.

## Reference solution and step estimate
- A: open the scan and the email, open Manage Track Changes, accept/reject 18 revisions one by one (or filter by
  author), delete 3 comments, save (Keep format), write the 4-line text file. ~35-50 actions; 15-20 min human.
- B: read the 2-page rider, add the definition, type the heading (apply Heading 1) and 5 paragraphs, renumber 5
  headings + 17 sub-clause numbers + 11 cross-references (Find & Replace, in descending order to avoid double
  increments, skipping "Clause 7"), update the survival list, Tools > Update All, save, export PDF. ~50-80 actions;
  25-35 min human.

## Self-test (node 0 simulated Guest, `tmp_o/test_o2.py`; reference = XML-level edits, PDF stand-in via PyMuPDF)
pristine A 0.0 / B 0.065; A->B: A 1.0, B 1.0; B->A: A 1.0, B 1.0; partial A "accept all" 0.57; partial B (clause +
headings, no cross-refs, TOC not updated) 0.78, A in that world 0.0.
Realism check on the dev box with real LibreOffice 24.2 through UNO (`lo_o2.py`): Writer opens the file with 18
redlines, 3 comments and a live TOC index; after Writer index update + docx save + PDF export, LO-saved pristine
scores A 0.0 / B 0.065; A->B and B->A (Writer saving in between) score 1.0 / 1.0 with 13/13 TOC page numbers
matching the exported PDF.

## Known risks
- LibreOffice splits a tracked change at run boundaries on save; the checker matches revisions by text fragments
  and checks outcomes on visible text, so split revisions are handled.
- A user who switches track-changes recording on before B's edits makes B's edits tracked insertions by the Guest
  user - B is still graded on visible text; A's checker only looks at the three reviewers.
