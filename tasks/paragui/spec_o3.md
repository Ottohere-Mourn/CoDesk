# Pair o3 - one grant proposal in Writer (+ its Calc budget): revised cost rules vs. funder formatting rules

Family F1 (office documents). Tasks `pgo3budget` (A) and `pgo3format` (B). Files: `build_o3.py`, `pg_o3.py`
(helpers `pg_olib.py`, scans `lib_oscan.py`), `task_pgo3budget.py`, `task_pgo3format.py`.

## Scenario and persona

Dr Amara Osei (University of Eastfield) is submitting a full proposal "TeleRehab-Home" to the (fictional) Northern
Health Research Fund. `~/Documents/Grant/NHRF_proposal_Osei.docx` (open in Writer) was drafted from a US
co-applicant's template: US Letter, 2 cm margins, Liberation Serif 12 pt applied as direct formatting on every run,
section headings as bold 14 pt *Normal* paragraphs, header "DRAFT - internal - do not circulate", no page numbers,
references unsorted. Section 5 contains a 9-row budget table and a justification that quote every figure; the cover
table quotes the amount requested (GBP 148,444.80). `NHRF_budget_Osei.xlsx` computes the budget from a Rates sheet.

- **A**: the funder's letter of 2 Oct 2026 (scan) changes the cost rules: indirect costs 20% -> 15%, RA salary capped
  at GBP 32,000, mileage GBP 0.45 -> 0.35, single equipment items > GBP 5,000 ineligible (the GBP 7,800 motion capture
  system must go). Update the workbook, then the proposal's budget table, justification text and cover amount (new
  total GBP 125,294.80), and leave a note.
- **B**: Annex C (scan, also carrying the application reference NHRF-2026-0417 that only appears there): A4, 2.5 cm
  margins, Liberation Sans/Arial 11 pt with 1.15 spacing, Heading 1 (14 pt bold) / Heading 2 (12 pt bold) styles,
  header = reference right-aligned (no draft marking), footer "Page X of Y" centred, references alphabetical with 1 cm
  hanging indent, <= 6 pages, PDF named `NHRF-2026-0417_Osei.pdf`.

Provenance: last-minute funder rule changes and "your proposal will be returned if it does not follow the formatting
annex" are routine in research-office work (UKRI/NIHR/ERC calls publish exactly such annexes; "page X of Y",
"hanging indent for references", "apply heading styles instead of manual bold" are classic Writer/Word support
questions).

## Requests (verbatim)

**A - pgo3budget**
> I'm Dr Amara Osei, PI of our grant application to the Northern Health Research Fund. The funder has just changed its cost rules; their letter is scanned at ~/Documents/Grant/NHRF_cost_rules_letter.pdf. Please bring our budget into line with it: update the budget workbook ~/Documents/Grant/NHRF_budget_Osei.xlsx (everything is calculated from its Rates sheet) and take out anything that is no longer eligible. Then make the proposal that is open in LibreOffice Writer (~/Documents/Grant/NHRF_proposal_Osei.docx) consistent with the revised budget: the budget table and the justification text in section 5, and the amount requested in the cover table. Save both files in place in their current formats, and leave me a short note in ~/Documents/Grant/budget_changes.txt with the new total and what you changed.

**B - pgo3format**
> I'm Dr Amara Osei, PI of our grant application to the Northern Health Research Fund. The full proposal is open in LibreOffice Writer (~/Documents/Grant/NHRF_proposal_Osei.docx). Please make it comply with the funder's formatting requirements in the scanned Annex C (~/Documents/Grant/NHRF_Annex_C_formatting.pdf): page size and margins, body text, heading styles, the header with our application reference, page numbers and the reference list - without changing the wording of the proposal. Save it in place as .docx and export the submission PDF into ~/Documents/Grant/ with the file name the annex asks for.

## Shared resources
`~/Documents/Grant/`: the proposal (opened once in Writer), the budget workbook, the two scans. Both tasks edit the
same open proposal; A additionally opens the workbook in Calc (same soffice process).

## Expected contention when run simultaneously
- B's typical moves are global: Ctrl+A + Clear Direct Formatting / set font size, changing the default paragraph
  style, Page Style dialog (modal), Header/Footer insertion. A meanwhile types numbers into the budget table and
  edits sentences in section 5: a select-all by B while A is typing replaces the whole document with A's keystrokes;
  B's modal dialogs swallow A's input; A switching to Calc and back moves the focus B relies on.
- A's numbers typed into runs that B has not yet normalised keep the old direct formatting (12 pt serif), and B's
  "clear direct formatting" can hit A's half-typed edits.
- Saving: either agent's save writes both agents' unsaved edits (fine) but script-based edits (python-docx) of the
  file collide with Writer's in-memory copy (last writer wins).

## GUI-only parts
- A: the new cost rules exist only in the scanned letter.
- B: the formatting requirements and the application reference exist only in the scanned annex; styles, page style,
  header/footer fields are Writer state best reached through the GUI.

## Grading (host side; `expected.json`)
**A - `evaluate_budget`** (1.0)
- 0.20 workbook: Rates salary 32000, mileage 0.35, indirect 0.15 (or 15) 0.05 each; motion capture line removed or
  zero 0.05 (formulas evaluated by `pg_olib.XBook`).
- 0.10 workbook total requested = 125,294.80.
- 0.30 proposal budget table: staff, travel, equipment, direct subtotal, indirect, total = new values, and the
  indirect row label says 15% (7 items).
- 0.10 cover table "Amount requested" = 125,294.80.
- 0.20 text: 7 fresh numbers present (0.08), 9 stale numbers absent (0.08: old total, salary, staff, travel,
  equipment, direct, indirect, 7,800, 0.45), every "N% of direct costs" says 15 (0.04).
- 0.10 note mentions the new total and the removed equipment.

**B - `evaluate_format`** (1.0)
- 0.05 A4; 0.10 margins 2.5 cm (left/right; top/bottom either as page margin or, as LibreOffice writes it when a
  header/footer is on, as header/footer distance).
- 0.10 share of body characters (incl. tables, excluding title and headings) at 11 pt; 0.05 share in Liberation
  Sans/Arial; 0.05 share of body paragraphs with 1.15 line spacing (effective values through style chain).
- 0.15 the 7 section headings use style Heading 1 with effective 14 pt bold; 0.05 the 4 sub-sections Heading 2 12 pt
  bold (numbers may be manual or automatic).
- 0.05 header contains NHRF-2026-0417; 0.03 no DRAFT/internal text; 0.02 right-aligned.
- 0.07 footer has PAGE and NUMPAGES fields and "Page .. of .." text; 0.03 centred.
- 0.05 references in alphabetical order of first author; 0.05 hanging indent 1 cm.
- 0.15 PDF `NHRF-2026-0417_Osei.pdf`: exists, <= 6 A4 pages, every page shows the reference and "Page X of Y"
  (1/3 each).

## Reference solution and step estimate
- A: read the letter, change 3 Rates cells and zero/delete the motion capture line in Calc, save; edit 6 table cells +
  1 label, ~6 numbers in the justification, delete the motion-capture phrase, edit the cover amount, save, write the
  note. ~40-60 actions; 20 min human.
- B: read the annex; Format > Page Style (A4, margins, header + footer on); type the reference right-aligned; footer
  "Page " + Insert > Field > Page Number + " of " + Page Count, centred; Ctrl+A, Clear direct formatting; modify Default
  Paragraph Style (Liberation Sans 11, proportional 115%); modify Heading 1/2; apply them to 11 headings; sort the
  8 references (Tools > Sort) and set the hanging indent; save; export PDF with the right name. ~50-70 actions;
  25 min human.

## Self-test (node 0 simulated Guest, `tmp_o/test_o3.py`)
pristine A 0.0 / B 0.0; A->B: A 1.0, B 1.0; B->A: A 1.0, B 1.0; partial A (workbook + table only) 0.77; partial B
(page/body/header/footer only; no heading styles, refs or PDF) 0.55.
Realism check with real LibreOffice 24.2 (dev box, `lo_o3.py`; B performed through the UNO API the way the GUI does
it, A in python): A->B 1.0 / 1.0, B->A 1.0 / 1.0, and after a further Writer re-save 1.0 / 1.0. This confirmed that
Writer stores "top margin 2.5 cm + header" as w:top=1831/w:header=1417 (handled), exports page fields as
`PAGE \* ARABIC` / `NUMPAGES \* ARABIC`, and writes several header parts.

## Known risks
- The body-text checks are proportional, so a few runs typed by A in the old direct formatting after B's clean-up
  cost B only a little (it is still correct to grade them as non-compliant).
- If B converts the manual "1." heading numbers to automatic chapter numbering, headings are still recognised.
