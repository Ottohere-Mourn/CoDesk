# Pair o1 - one Calc workbook: September invoices vs. budget variance analysis

Family F1 (office documents). Tasks `pgo1invoices` (A) and `pgo1variance` (B). Files: `build_o1.py`, `pg_o1.py`
(shared helpers in `pg_olib.py`, scan rendering in `lib_oscan.py`), `task_pgo1invoices.py`, `task_pgo1variance.py`.

## Scenario and persona

Elena Marsh is the operations manager of Harbourside Community Health, a small UK community health provider. The
quarterly operations budget is a single workbook, `~/Documents/Ops_Budget_2026Q3.xlsx`, with these sheets:
- **Budget**: six cost centres with original Q3 budget, an empty "Approved transfers" column and a formula
  "Revised Q3 budget" column.
- **Actuals**: the July and August invoices (23 rows, budget charge column = `IF(cost centre = 410, gross, net)`).
- **Codes**: the cost-centre table (the department printed in the invoice's "Deliver to" block) and the GL accounts.

It is the end of September. Two chores are given at the same time:
- **A** (accounts payable): the September post was scanned into `~/Documents/invoices/inbox` (15 image-only PDFs).
  Book them into Actuals per the finance office's rules (`~/Documents/invoices/AP_coding_rules.txt`), file the PDFs,
  and explain what was not booked.
- **B** (reporting): tomorrow is the quarterly operations review. Apply the CFO's virement decisions (scanned memo
  `~/Documents/BT-2026-07_budget_transfer.pdf`) to the Budget sheet and build a live variance analysis with
  conditional formatting, a chart and a short note.

Provenance: the monthly "key the supplier invoices into the budget tracker" job of a finance assistant and the
"budget vs. actuals with traffic lights" view prepared for budget holders are two of the most common spreadsheet
workflows in small organisations (cf. the many "SUMIF budget vs actual" / "conditional formatting over budget"
questions on SuperUser and the Microsoft/LibreOffice forums). The AP rules (VAT recovery except for VAT-exempt
clinical activity, credit notes as negative rows, quotes are not invoices, period cut-off, duplicates) are standard UK
accounts-payable practice.

## Requests (verbatim)

**A - pgo1invoices**
> I'm Elena Marsh, operations manager at Harbourside Community Health. Our Q3 operations budget workbook ~/Documents/Ops_Budget_2026Q3.xlsx is open in LibreOffice Calc. The September supplier invoices have just been scanned into ~/Documents/invoices/inbox - please book them into the Actuals sheet (July and August are already there), following the finance office's coding rules in ~/Documents/invoices/AP_coding_rules.txt: one row per invoice with posting date, invoice number, vendor, description, cost centre (from the 'Deliver to' department), GL account (see the Codes sheet), net, VAT, gross and budget charge. The rules also say how to treat credit notes, duplicates, quotations and anything that does not belong to Q3. Move every PDF you book into ~/Documents/invoices/booked, and list the documents you leave in the inbox, each with the reason, in ~/Documents/invoices/inbox/NOT_BOOKED.txt. Save the workbook in place, keeping the .xlsx format.

**B - pgo1variance**
> I'm Elena Marsh, operations manager at Harbourside Community Health, and I need the Q3 budget-versus-actuals view for tomorrow's operations review. Our workbook ~/Documents/Ops_Budget_2026Q3.xlsx is open in LibreOffice Calc. (1) The CFO's decisions on our virement requests are in the scanned memo ~/Documents/BT-2026-07_budget_transfer.pdf: enter the approved transfers (only those) in the 'Approved transfers' column of the Budget sheet, positive for the receiving and negative for the giving cost centre, so that the 'Revised Q3 budget' column updates. (2) Add a sheet named 'Variance' with one row per cost centre: code, name, revised budget, actual spend, variance (actual minus revised budget) and variance % (variance divided by revised budget). Actual spend is the total of the 'Budget charge' column of the Actuals sheet for that cost centre; the September invoices are still being keyed into Actuals, so use formulas that also pick up rows added later, not typed-in numbers. (3) Use conditional formatting to show the variance % in red for every cost centre that is more than 10% over its revised budget, and put a column chart comparing revised budget and actual per cost centre on the Variance sheet. (4) Add a sheet named 'Notes' with a short paragraph for the meeting that names the cost centre(s) more than 10% over budget and cites the memo reference. Save the workbook in place as .xlsx.

## Shared resources (setup, identical for both tasks, idempotent)
- `~/Documents/Ops_Budget_2026Q3.xlsx`, opened once in LibreOffice Calc (`_open_setup`; the second setup only
  re-focuses the same window).
- `~/Documents/invoices/{AP_coding_rules.txt, inbox/*.pdf (15), booked/}`, `~/Documents/BT-2026-07_budget_transfer.pdf`.

## The September post (A), all image-only scans (grey, skewed, speckled, some with RECEIVED stamps)
| file | document | booking |
|---|---|---|
| scan_20260903_0001 | MediWholesale MW-77310, Pharmacy / Clinic Stores | 410 / 6400, net 6,850.00, VAT 1,370.00, charge = gross 8,220.00 |
| Invoice_SP-22790 | Sparkle Pro SP-22790, deep clean after flood, Housekeeping | 220 / 6150 |
| scan_20260908_0002 | Hexagon HX-5520, planned maintenance + lift inspection, Estates | 210 / 6100 |
| scan_20260909_0003 | TechServe TS-10483, network switch, IT Service Desk | 310 / 6300 (vendor also works for Reception - code by department) |
| Voxline_bill_Sep2026 | Voxline VX-SEP26-118, telephone & broadband | 310 / 6350 |
| scan_20260911_0007 | **duplicate** scan of TS-10483 (stamped COPY) | not booked |
| scan_20260912_0004 | Northline 0093114 (leading zeros), emergency call-out + lighting | 210 / 6100 |
| scan_20260915_0005 | **credit note** CN-0412 (Hexagon) | 210 / 6100, negative -400 / -80 / -480 |
| OfficeDirect_OD-55102 | toner, paper, badges, Reception | 110 / 6500 (net 865.40, VAT 173.08) |
| scan_20260918_0006 | ClinicSource PH-2291, sterile packs | 410 / 6400, charge = gross |
| scan_20260922_0008 | Quayside PR-3307, patient leaflets, Reception | 110 / 6500 |
| Okonkwo_invoice_114 | J. Okonkwo Training 2026-114, **not VAT registered** | 510 / 6600, VAT 0 |
| Invoice_SP-22817 | Sparkle Pro SP-22817, contract cleaning September | 220 / 6150 |
| scan_20261002_0009 | Voxline VX-OCT26-131 dated **1 Oct 2026** | not booked (Q4) |
| scan_20260929_0010 | Hexagon **QUOTATION** Q-8841 | not booked |

The CFO memo (B) approves 510->210 4,000, 110->210 2,000, 220->310 1,500 and **declines** 510->410 3,000.
Data are designed so that exactly cost centre 210 (Facilities Maintenance) is >10% over its revised budget both
before (116%) and after (127%) the September invoices are keyed in; 310 is over budget but below 10% only if the
transfers are applied (107.6% vs 118%).

## Expected contention when run simultaneously
- Both agents edit **the same open Calc document**: A types rows in Actuals while B switches sheets, inserts a new
  sheet, opens the conditional-formatting dialog and the chart wizard (modal dialogs block A's typing; a sheet switch
  by B sends A's keystrokes into the wrong sheet, e.g. into the new Variance sheet).
- Saving: either agent's Ctrl+S saves both agents' unsaved work (good), but "Keep current format" dialogs pop up for
  the other agent; an agent that edits the .xlsx with a script (openpyxl) while the document is open in Calc is
  silently overwritten by the next save from Calc, or overwrites the other's Calc work if it saves after.
- Content dependency: B's actuals must be formulas over Actuals because A is appending rows; typed numbers computed
  before A finishes are stale and fail B's check (graded against the final Actuals sheet).

## GUI-only parts
- A: all invoice data exist only as pixels (15 scans, three of which must be recognised as not bookable).
- B: the virement decisions (including the declined one) and the memo reference exist only in the scanned memo.
- Calc application state (the open document) is shared; formulas / conditional formatting / chart can be done in the
  GUI or by script (realistic), but scripted edits collide with the open Calc window.

## Grading (host side, from the saved .xlsx + Guest file tree; ground truth in `assets/o1/expected.json`)
Formulas are evaluated on the host by `pg_olib.XBook` (SUM/SUMIF(S)/IF/VLOOKUP/INDEX/MATCH/SUMPRODUCT/... subset,
whole-column ranges, cross-sheet refs) so files last written by openpyxl (no cached values) and by LibreOffice (cached
values, used as fallback for unsupported functions) are graded alike.

**A - `evaluate_invoices`** (1.0)
- 0.60: 12 expected bookings, matched by invoice number (case/punctuation/leading zeros ignored); per booking 0.2
  present + cost centre 0.2 + GL 0.15 + net/VAT/gross 0.25 + budget charge 0.1 + posting date 0.1.
- 0.10: duplicate booked at most once, October invoice not booked, quotation not booked (only counted once >= 6
  bookings have the right net amount).
- 0.05: the 23 July/August rows are intact (same condition).
- 0.12: PDFs moved: 0.7 x (booked invoices found by md5 in `invoices/booked/`) + 0.3 x (Q4 invoice and quotation
  still in the inbox, exactly one of the duplicate pair in booked).
- 0.13: `NOT_BOOKED.txt` names each of the 3 unbooked documents (file name or document number) and a reason
  (duplicate / October-Q4 / quotation).
- Cap: fewer than 6 bookings with the right net amount -> score <= 0.4.

**B - `evaluate_variance`** (1.0)
- 0.20: Budget sheet: revised budget = original + approved transfers for all 6 cost centres (original unchanged).
- 0.40: Variance sheet, per cost centre (found by its code in columns A-C): actual = sum of budget charge in the
  FINAL Actuals sheet and the cell is a formula that refers to Actuals (directly or through cells) 0.5; variance
  (either sign) 0.25; variance % (fraction or percent) 0.25.
- 0.15: a conditional format covering all variance-% cells, with a fill/font style, that fires exactly for the cost
  centres more than 10% over budget in the final data (cellIs rules and expression rules are evaluated); 0.33 if a
  rule covers the cells but flags the wrong set.
- 0.10: a chart anchored on the Variance sheet (0.5 if a chart exists elsewhere).
- 0.15: Notes sheet: >= 25 words, names cost centre 210 / Facilities Maintenance, cites BT-2026-07.
- Cap: no Variance sheet -> score <= 0.3.

## Reference solution (what `test_o1.py` does) and step estimate
- A: open each scan in the PDF viewer, read and key 12 rows (posting date, number, vendor, description, CC, GL, net,
  VAT, gross; copy the J formula), skip the duplicate/Q4/quote, save as .xlsx (Keep format), move 12 PDFs in Files or
  a terminal, write NOT_BOOKED.txt. A strong GUI agent: ~60-90 actions (15 documents x 2-3 views + 12 rows typing +
  file moves); ~30 min for a human.
- B: read the memo, type 5 transfer values, insert a sheet, enter 6 rows of `SUMIF(Actuals!$E:$E;A2;Actuals!$J:$J)`
  style formulas, Format > Conditional > Condition "greater than 0.1" with a red style, Insert > Chart (column), Notes
  sheet, save. ~40-60 actions; ~20-30 min for a human.

## Self-test (offline, simulated Guest on node 0; `tmp_o/test_o1.py`)
pristine A 0.024 / B 0.033; reference A->B: A 1.0, B 1.0; B->A: A 1.0, B 1.0; partial A (quote + duplicate booked,
IT coded to 110, net charge for clinical, files not moved) 0.48; partial B typed actuals before A's rows (B->A) 0.60;
partial B without CF/notes 0.70. Additionally (dev box, real LibreOffice 24.2 through UNO): the A->B workbook
round-tripped through Calc (recalculated, saved as xlsx) scores 1.0 / 1.0 via the cached-value path, and B done
natively in Calc (`lo_extra.py`: SUMIF over `$Actuals.$E$2:$E$500`, conditional format "greater than 0.1" with the
built-in cell style *Bad*, a native column chart, then saved as xlsx) scores B 1.0 / A 1.0 in both orders.

## Known risks
- An en-US Calc parses typed "12/09/2026" as 9 December: the posting-date sub-check (0.06 of A) then fails, which is
  a genuine data error; dates typed as text "30/09/2026" are accepted.
- Exotic formulas outside the evaluator subset fall back to LibreOffice's cached values; if the file was last written
  by openpyxl such cells cannot be verified (counted as wrong).
