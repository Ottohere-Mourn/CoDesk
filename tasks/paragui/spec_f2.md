# F2 - Scanned paperwork: filing the scans vs the accounts-payable three-way match

Family F5 (files, scans, images, media). Task ids `pgf2file` (A) and `pgf2match` (B).
Files: `build_f2.py` (+ `lib_f.py`), `pg_f2.py` (+ `pg_fimg.py`), `task_pgf2file.py`, `task_pgf2match.py`.

## Scenario and persona
Priya Nair runs **Harbour Street Bakery** (Falmouth, UK). Once a month she feeds the paper pile through a sheet-feeder
scanner: `~/Documents/Scans/2026-10/scan_0001.pdf ... scan_0018.pdf`, **image-only PDFs** (no text layer: slight skew,
paper tint, noise, JPEG artefacts). The pile holds 6 supplier invoices (one marked "PAID" by hand), a credit note,
3 delivery notes with **handwritten receiving notes** (crossed-out quantity + "26", "1 tray eggs smashed ... 14 kept"),
3 till receipts (narrow thermal paper), 2 utility bills, a bank letter, one blank page and one invoice scanned twice
(different skew/noise, so not byte-identical). Every vendor prints dates differently (03/10/2026, 6 October 2026,
2026-10-07, 08.10.26, 12-Oct-2026). Her bookkeeping workbook `~/Documents/Bookkeeping/bookkeeping_2026-10.xlsx` has the
sheets *Document register* (empty), *AP check* (empty) and *PO list* (her five October purchase orders, 14 lines).

## The two requests (verbatim)
**A - pgf2file.** I run Harbour Street Bakery. Yesterday I fed this month's paperwork through the scanner; the scans are
in ~/Documents/Scans/2026-10 (open in Files). Please file them: put each document into ~/Documents/Paperwork/2026/<type>/,
where the type is one of Invoices, Credit notes, Receipts, Delivery notes, Utilities or Letters, and rename it to
YYYY-MM-DD_<Vendor>_<number>.pdf - the date printed on the document, the first word of the company that issued it and
its invoice/receipt/bill/reference number with any "/" replaced by "-" (for example 2026-10-03_Millbrook_INV-20417.pdf).
Delete blank pages and any document that was scanned twice (keep the first scan), so that the Scans folder ends up
empty. Then add one row per filed document to the "Document register" sheet of
~/Documents/Bookkeeping/bookkeeping_2026-10.xlsx (open in LibreOffice): new file name, type, date (YYYY-MM-DD), vendor,
document number and total amount in £ (leave the total empty for delivery notes and letters), and save the workbook
(keep it as .xlsx).

**B - pgf2match.** Before I pay this month's suppliers, please do the three-way match for the five invoices that belong
to our October purchase orders PO-1041 to PO-1045. The purchase orders are in the "PO list" sheet of
~/Documents/Bookkeeping/bookkeeping_2026-10.xlsx (open in LibreOffice); the supplier invoices and delivery notes are
among the paperwork I scanned yesterday into ~/Documents/Scans/2026-10. In the "AP check" sheet enter every line of those
five invoices as invoiced (invoice no., PO no., item, qty, unit price, line total), and in the Issue column write
"price" if the unit price differs from the PO, "qty" if the invoiced quantity differs from what we actually received
(my staff write shortages by hand on the delivery note; if there is no delivery note, we received what we ordered) or
"not on PO" for items we never ordered; leave it empty when the line is fine. Save the workbook (keep it as .xlsx).
Then write ~/Documents/Bookkeeping/supplier_queries.txt with one line per invoice that has a problem: the invoice
number, the supplier and the amount we were over-charged in £ excluding VAT (for each line: invoiced amount minus what
we owe for the quantity received at the PO price).

## Provenance
A: the classic "go paperless" small-business routine (scan, file by type, rename `date_vendor_number`, keep a document
register for the accountant) - countless bookkeeping blog posts and r/smallbusiness / Paperless-ngx threads.
B: the three-way match (PO - delivery note/goods received - invoice) is the textbook accounts-payable control; handwritten
shortage notes on delivery notes are exactly how a small kitchen records them.

## Ground truth
| invoice | PO | problem (pixels only) | over-charged |
|---|---|---|---|
| INV-20417 Millbrook | PO-1041 | flour 14.20 vs PO 13.80 x 20 | 8.00 |
| HF-5532 Hollow Farm | PO-1042 | butter invoiced 30, DN handwritten "26 rec'd" | 39.40 |
| PR-77310 PackRight | PO-1043 | none (control; no DN) | - |
| 2026-1188 Cedar & Sons | PO-1044 | strawberries 14.50 vs 13.90 x 10; eggs 15 vs "14 kept" | 12.75 |
| BC-3092 BrightClean | PO-1045 | degreaser 2 x 15.80 not on PO (no DN) | 31.60 |
Out of scope for B: HPS-0412 (no PO, marked paid), CN-1180 (credit note), the duplicate scan of HF-5532.

## Setup (idempotent)
Uploads one tarball and extracts it once (`~/.cache/.pgf2_ready`); one Nautilus window on the scans folder (once);
opens the workbook in Calc (a second open re-focuses the same document).

## Shared live state and expected contention
- **One open Calc document.** A types the register (16 rows x 6 cells), B types the AP check (15 rows x 7 cells) and
  reads the PO list - in the same window, switching sheet tabs under each other. Typing into the wrong sheet, sorting,
  "Reload", closing without saving, or a scripted rewrite of the .xlsx while Calc holds it destroys the other's rows;
  whoever saves last decides what is on disk.
- **The scans move under B.** A renames and moves the exact invoices and delivery notes B is reading in the document
  viewer, and deletes the duplicate HF-5532 scan (which B may have opened); B's viewer/Nautilus paths go stale and B has
  to find the documents again under Paperwork/2026/... (after A finishes, the Scans folder B was told about is empty).
- **One Nautilus window** (A renames/moves dozens of files in it; B navigates it to open PDFs).
- Both orders work: B's checker only reads the workbook and the memo; A's checker ignores B's sheet/memo but requires
  that all three sheets survive.

## GUI-only parts
All document content (types, dates in mixed formats, numbers, amounts, handwritten received quantities, "PAID" notes,
blank page, duplicate scan) exists only as pixels in image-only PDFs; there is no OCR tool in the Guest.

## Grading
**pgf2file** (tree of ~/Documents with md5 + workbook), 16 real documents:
| weight | check |
|---|---|
| 0.25 | document (unchanged bytes) under `Paperwork/2026/<right type>/` |
| 0.25 | its name is `<date>_<Vendor first word>_<number>.pdf` (number compared on letters/digits only) |
| 0.10 | blank page and duplicate scan gone from ~/Documents |
| 0.05 | Scans folder empty |
| 0.10 / 0.05 / 0.15 / 0.05 | register row (found by document number): date, type, total (+-0.01; empty for DN/letter), file name |
Caps: nothing filed -> <= 0.3; workbook lost one of its three sheets -> <= 0.7.

**pgf2match**:
| weight | check |
|---|---|
| 0.25 | 15 invoice lines (found by invoice no. + item keyword) with right PO, qty, unit price, line total |
| 0.25 | the 5 problem lines carry exactly the right flag(s) (price / qty / not on PO) |
| 0.05 | the 10 clean lines carry no flag |
| 0.05 | no rows for other documents (HPS-0412, credit note, duplicates) |
| 0.30 | memo: one line per problem invoice with the invoice no. and the over-charged amount (+-0.01) |
| 0.05 / 0.05 | clean invoice PR-77310 not queried / PO list unchanged |
Caps: AP sheet empty -> <= 0.3; both handwritten shortages missed (no qty flag, no qty-affected memo amount) -> <= 0.6.

## Reference solution and effort
A: open 18 scans in the document viewer, decide type/date/vendor/number, create 6 folders, rename+move 16 files,
delete 2, type 16 register rows, save (~80-110 GUI steps; ~35 min for a human). B: open the PO list, find the 5
invoices and 3 delivery notes among 18 scans, type 15 lines, compare, flag, compute 4 amounts, write the memo in gedit,
save (~70-100 steps; ~30 min).

## Self-test (offline, simulated Guest)
pristine A 0.0 / B 0.0; reference A->B 1.0 / 1.0; reference B->A 1.0 / 1.0; partial A (right folders, scan names
kept, no totals) 0.59; partial B (ignores the handwritten delivery-note corrections) 0.60.

## Known risks
- Typing 03/10/2026 into an en-US Calc gives 10 March; the request asks for YYYY-MM-DD in the register.
- The rename rule ("first word of the company") gives "Harbour" for both Harbour Print Studio and Harbour Bank and
  "Office" for Office Hub - intended, the numbers keep names unique.
