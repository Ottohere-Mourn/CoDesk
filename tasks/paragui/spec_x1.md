# X1 - Month-end close at a small coffee roaster (`pgx1recon`, `pgx1report`)

Family F6 (cross-application workflows). Files: `build_x1.py`, `app_x1.py`, `pg_x1.py`, `task_pgx1recon.py`,
`task_pgx1report.py`, shared helpers `lib_x.py` (build), `pg_xcommon.py` (evaluation), `lib_xtest.py` + `lib_xtest_x1.py`
(offline self-test).

## Scenario and persona

Sam Whitaker is the office & finance manager of **Harbour & Pine Coffee Roasters Ltd**, a 12-person roastery in
Falmouth (UK) that sells wholesale to cafés and offices, runs an online shop (Shopify payouts are invoiced to
"Shopify Payments") and sells barista training and machine servicing. Bookkeeping lives in **Ledgerline**, the
company's intranet accounting app (sales invoices with VAT, customer receipts, monthly sales reports, board-pack
uploads). It is 2 October 2026; September has to be closed. Two people want something from Sam on the same morning:

- Priya Shah, the external accountant, wants the **September bank reconciliation** in her template.
- Tom Reyes, the director, wants the **September management report** for Thursday's directors' meeting.

Sam hands one chore to each assistant. Both run on Sam's desktop: one Thunderbird (sam.whitaker@harbourpine.co.uk,
offline POP profile), one Chrome with Ledgerline open (both log in as `sam`), LibreOffice.

## The two requests (verbatim task instructions)

**A - `pgx1recon`**
> It's month-end at Harbour & Pine and our accountant Priya needs the September bank reconciliation - her email
> 'September close - bank reconciliation' in Thunderbird has the template and her rules, and Tom emailed me a scan of
> the paper bank statement. Please record every customer payment on the statement against the right invoice in
> Ledgerline (http://127.0.0.1:8121, username sam, password HarbourPine26), dated the day the money arrived. Customers
> often quote the wrong invoice number, so check who paid and how much; split a transfer that pays several invoices,
> and don't post anything twice. Save the completed template as ~/Documents/Finance/Bank_Rec_2026-09.xlsx and reply to
> Priya's email with it attached, listing the unmatched items and anything still owed after a short payment, with
> amounts. Leave the reply in Drafts - don't send it.

**B - `pgx1report`**
> Tom wants the September management report - his email 'September management pack' in Thunderbird says what goes in
> it. Take all figures from the Reports page of Ledgerline (http://127.0.0.1:8121, username sam, password
> HarbourPine26). Keep the numbers and the column chart in ~/Documents/Reports/Mgmt_Pack_2026-09.xlsx, write the report
> in LibreOffice Writer and save it as ~/Documents/Reports/Management_Report_2026-09.docx, export it to
> Management_Report_2026-09.pdf in the same folder, upload that PDF to Ledgerline as the September 2026 board pack, and
> reply to Tom's email with the PDF attached. Leave the reply in Drafts - don't send it.

## World state after setup

- **Ledgerline** (`app_x1.py`, port 8121, db `~/.local/share/intranet/ledgerline/app.db`): 15 customers, 72 invoices
  INV-2026-0371..0442 (1 Jul - 2 Oct, net + 20% VAT, three channels), 38 receipts recorded up to 1 Sep (the Oak & Anchor
  receipt of 1 Sep was entered by Tom), one void duplicate (0400, voided by Priya on 24 Sep), two earlier board packs.
  Header **period selector** (Jul/Aug/Sep/Oct 2026, All periods) defaults to the business month (October) at login and
  is stored **in the login session**, as are the invoice-list filters (status, search, page). Invoice list, receipts
  and reports are scoped to that period. Receipts are recorded on the invoice page (date, amount, method, reference);
  overpayments are refused. Board packs: list + multipart PDF upload. Activity log of every change.
- **Thunderbird** Inbox (13 mails): Tom's scan of the paper statement (`Northshore_Statement_Sep2026.pdf`, 2 pages,
  image-only), Priya's request with `Bank_Rec_Template.xlsx`, Tom's "September management pack", remittance advice
  from Kestrel (paid 0434 although the bank reference says 0433), The Copper Kettle explaining a £120 deduction on 0421,
  Jess Morgan's £250 course deposit (no invoice), Larkspur saying their overdue 0405 is paid on 7 Oct, two Shopify
  payout notices, newsletters/orders. Sent: last month's management report PDF to Tom and last month's filled rec to
  Priya (format examples; the August pack still contains the later-voided 0400).
- Chrome: tab on Ledgerline's login page. Folders ~/Documents/Finance and ~/Documents/Reports exist.

## What each task needs (the reference solution)

**A**: read Priya's rules and open the scanned statement (2 pages, 12 money-in lines among 13 debits); log in; set
the period to All/Aug/Sep; for each credit find the invoice: exact references (0402, 0425), a transfer paying two
Marlow invoices (split 922.80 + 762.00), a Shopify payout matched by amount, Northgate's unreferenced £1,560 (Larkspur's
overdue 0405 has the same amount - wrong customer), Copper Kettle's short payment (£600 of £720, £120 outstanding),
Kestrel quoting the wrong number (0433 belongs to Saltmarsh; the remittance mail says 0434; posting 1,212 on 0433 is
refused as an overpayment), Greenway's reference that is no invoice number, Oak & Anchor already posted by Tom, HMRC
VAT repayment and a course deposit that are not invoice payments. 10 receipts are recorded with the bank dates.
Then the template is saved from the mail, filled in Calc (statement summary from the scan + 12 rows with invoice
numbers and status Posted / Already posted / Unmatched), saved as xlsx, and a reply to Priya is drafted with the
workbook attached, naming the VAT repayment £2,145.30, the £250.00 deposit and the £120.00 still owed by The Copper
Kettle. About 70-90 GUI steps (10 receipt forms alone are ~50 actions).

**B**: read Tom's mail; in Ledgerline switch the period to July, August, September in turn and copy the channel table
(net revenue, invoice counts) and the per-customer table of each month; sum per customer for Q3 and drop Shopify; build
the table + Q3 total + clustered column chart in Calc; write the Writer report (table, chart, Sep vs Aug % change
+15.9%, top three customers Blue Door Café / Fieldfare Hotel / Marlow Deli & Co with Q3 totals, 23 invoices issued in
September), save docx, export PDF; upload the PDF in Board packs with period September 2026; reply to Tom's mail with
the PDF attached and save as draft. Traps: "All periods" includes October; August must be taken from Ledgerline now
(0400 voided after last month's pack, which still shows the old figure). About 60-80 GUI steps.

## Shared live state and expected contention

- **One Ledgerline session in one Chrome.** The period selector is a session setting: when B switches to July to read
  the July report, A's invoice list (and the receipt page) silently changes to July - A suddenly cannot find 0425, or
  works in the wrong period; when A switches to All periods, B's report shows the whole year. Invoice-list filters
  (status/search/page) are also per session. Logging out (or a re-login that replaces the cookie) kills the other's
  session. Both tasks use the same tab strip; B's upload dialog and A's receipt forms are in the same window.
- **One Thunderbird.** Both read mails in the same Inbox and both compose replies (two compose windows, two save-as-draft
  operations, attachment pickers). Restarting Thunderbird (a common recovery move) closes the other's compose window
  and loses its unsaved draft.
- **LibreOffice**: A edits the template in Calc while B builds the pack in Calc and writes in Writer - one soffice
  process; a crash/"recover documents" dialog or closing LibreOffice affects both.
- No zero-sum element: A only changes receipts; B only reads reports (revenue is recognised on invoice date, receipts
  do not change it) and adds a board pack. Each checker accepts the other's changes (verified in both orders).

## Grading

`evaluate_recon` (A) - Ledgerline db (`sql`), the workbook (fetched, header-driven parse), Drafts/Sent (`MAILX`,
attachments fetched and opened):

| weight | sub-check |
|---|---|
| 0.40 | 10 expected receipts present: right invoice, amount to the penny, date = bank date (fraction) |
| 0.10 | no receipt on another invoice, no duplicate, no seeded receipt deleted (and at least one correct receipt) |
| 0.20 | workbook: one row per statement credit (found by amount) with exactly the right invoice numbers and status (1 / 0.5 / 0 per row, 12 rows) |
| 0.10 | workbook statement summary: opening, total paid in, total paid out, closing (4 values) |
| 0.10 | reply to Priya contains an xlsx attachment that holds >= 10 of the credit amounts and the closing balance (cross-check: the attachment is the rec, not any file) |
| 0.075 | reply text mentions 2,145.30, 250.00 and 120.00 |
| 0.025 | it is a reply (In-Reply-To/References Priya's message) |

Caps: no correct receipt in Ledgerline -> <= 0.3; workbook missing/unreadable -> <= 0.5.

`evaluate_report` (B):

| weight | sub-check |
|---|---|
| 0.12 / 0.04 / 0.06 | Mgmt_Pack xlsx: 9 channel-month values to the penny / 3 monthly totals + Q3 total / a chart object |
| 0.04 / 0.06 | docx exists with text / docx contains a chart, image or embedded object |
| 0.04 | the PDF exists and is a PDF |
| 0.10 | PDF text has the 9 channel-month values |
| 0.04 / 0.04 | PDF has September total / the % change vs August (±0.05) |
| 0.06 / 0.03 | top-3 customers named in order / with their Q3 amounts |
| 0.03 | September invoice count (23) stated next to "invoices" |
| 0.14 | a board pack for period 2026-09 uploaded in Ledgerline whose PDF contains the September total (db row + uploaded file) |
| 0.15 / 0.05 | draft to Tom with a PDF attachment containing the September total / it is a reply to Tom's mail |

Caps: no report PDF anywhere (file, upload, attachment) -> <= 0.3; figures wrong in the PDF (any channel value, the %
change or the top-3 order) -> <= 0.75.

## Self-test (offline, node 0, `lib_xtest_x1.py`)

Simulated Guest home, real `app_x1.py` under python3.10 on a free port driven over HTTP (login, period switches,
receipt forms, multipart upload), Thunderbird emulated on the mbox files, both setups run twice (idempotency). The
report reference solution scrapes Ledgerline's report pages and asserts they equal expected.json.

| run | recon | report |
|---|---|---|
| pristine | 0.0 | 0.0 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference) | 1.0 | 1.0 |
| A sloppy (Northgate money on Larkspur, ignored short payment, today's date once, skipped Kestrel, duplicate 0398, closing-balance typo, terse reply) / B stale (August from last month's pack) | 0.54 | 0.75 |
| A only posted in the app / B without chart, without reply | 0.5 | 0.68 |

## Provenance

Bank reconciliation against an invoice register (matching remittances with wrong/missing references, split and short
payments, non-sales credits such as HMRC VAT repayments) is the standard month-end task of small-business bookkeepers
(cf. QuickBooks/Xero "reconcile" workflows and the many accounting.stackexchange / r/Bookkeeping questions about
customers paying several invoices in one transfer or quoting the wrong invoice). The monthly management pack (revenue by
channel, chart, top customers, % change, PDF to the directors and the board-pack portal) is the usual companion task.

## Known risks

- Chrome's `<input type=date>` takes keyboard input in the locale order (mm/dd/yyyy on an en-US Guest); a mistyped
  date fails that receipt's check (by design: the date is part of the reconciliation).
- The agent may save the rec as .ods or under another name -> the workbook checks fail (path is given verbatim).
- PDF text extraction of a Writer export with a table is reliable; a report that contains only an image of the table
  would fail the text checks.
