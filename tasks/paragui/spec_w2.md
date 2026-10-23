# W2 — one expense portal, one browser session: approving the team's reports vs filing a trip report

Pair id `w2`, tasks `pgw2approve` (A) and `pgw2claim` (B). App: **Fenwick Spend — Expenses & Approvals**
(`app_w2.py`, stdlib http.server + sqlite3), served in the Guest at `http://127.0.0.1:8102` by
`pg_common.start_webapp`. Both tasks log in as the same user (`dana.okafor` / `Fenwick-Spend-26`) in the same Chrome.

## Persona and scenario
Dana Okafor is Marketing Director at Fenwick & Hale (consumer goods, Minneapolis). Thursday 22 Oct 2026: twelve expense
reports from her five-person team are waiting for her approval, and she still has to file her own report for last
week's Kestrel Foods visit in Chicago — Finance also wants the list of the department's approved October reports.

## The two requests (verbatim)
**A — pgw2approve**
> I'm Dana Okafor, Marketing Director at Fenwick & Hale. Twelve expense reports from my team are waiting for my
> approval in Fenwick Spend, our expense portal (http://127.0.0.1:8102, open in Chrome; log in as dana.okafor, password
> Fenwick-Spend-26 - approvals are in the Approver view). Please go through each of them and approve or reject it
> according to our travel & expense policy (Fenwick_TE_Policy_2026.pdf in my Documents folder), checking every line
> against its receipt. When you reject a report, say in the comment exactly what is wrong. Finally, save a short
> summary as ~/Documents/approvals_2026-10-22.txt with one line per report: the report number (EXP-...), Approved or
> Rejected, and the reason for each rejection.

**B — pgw2claim**
> I'm Dana Okafor, Marketing Director at Fenwick & Hale. Please file my expense report for the Kestrel Foods client
> visit in Chicago (14-16 Oct 2026) in Fenwick Spend, our expense portal (http://127.0.0.1:8102, open in Chrome; log in
> as dana.okafor, password Fenwick-Spend-26). The receipts for the trip (flights, hotel, two taxi rides and the client
> dinner) are in my Downloads folder. Create a report titled "Chicago - Kestrel Foods visit, 14-16 Oct", add one line
> per receipt with the date, category, merchant and amount in USD, attach each receipt to its line, and submit the
> report for approval. The dinner on the 15th was me plus three people from Kestrel Foods; wine is not reimbursable,
> so claim only the food and soft drinks. Then export the Marketing department's approved reports for October 2026
> from the Reports page as CSV and save the file as ~/Documents/marketing_approved_oct2026.csv.

## What is in the Guest after setup (idempotent `setup`, documents placed once via a marker file)
- Fenwick Spend on :8102, seed db: 12 users, 52 reports (40 historical Sep/Oct: Paid/Approved/Rejected/Submitted to
  other approvers; 12 waiting for Dana), ~85 receipt images stored as BLOBs.
  Header **role switcher "Employee view | Approver view" stored in the session**. Employee view: My reports, New
  report, report editor (line form with multipart receipt upload, attach receipt to an existing line, delete line,
  submit, recall). Approver view: Approvals queue + recently decided, review page (receipt thumbnails → full size,
  Approve / Reject with comment, reject needs a comment), Reports list (search, status / month-submitted / department /
  employee filters, sortable, paginated, **remembered per session**) with "Export CSV" that exports **the session's
  current filter**. Log out link. Self-approval impossible (Dana's reports go to Victor Hale).
- `~/Documents/Fenwick_TE_Policy_2026.pdf` — scanned (image-only) 2-page policy.
- `~/Downloads/`: `eticket_NL5KQ2.pdf`, `Folio_LakeshoreGrand_88231907.pdf` (image-only PDFs),
  `IMG_20261014_092733.jpg` (photo of a cab receipt), `Zipp_receipt_Oct16.png` (ride-share app screenshot),
  `IMG_20261015_221047.jpg` (photo of the itemized dinner receipt incl. wine) + two unrelated files
  (`IMG_20260922_131205.jpg` a September lunch, `Kestrel_Foods_meeting_agenda.pdf`).
- Chrome open on the portal's login page.

## GUI-only information
- Every amount/date/item A must check is only in receipt pixels (thermal-receipt photos, folio/e-ticket/rental
  documents, an order-confirmation screenshot) shown in the logged-in review page; the policy is an image PDF.
- B's amounts/dates/merchants exist only in the five receipt images/PDFs; the dinner's food subtotal (186.40) must be
  computed from the itemized lines (wine 108.00 of 294.40). Uploads go through Chrome's file chooser.
- The approved-reports list exists only behind the Approver view of the portal.

## Ground truth (A) — 7 approve, 5 reject
| report | employee | content | decision | why |
|---|---|---|---|---|
| EXP-2041 | Leo Marsh | cab 38.40 (receipt ok) + lunch 22.50 without receipt | Approve | < $25 needs no receipt |
| EXP-2042 | Aisha Bello | OfficeHub supplies claimed 248.20 | **Reject** | receipt total 184.20 |
| EXP-2043 | Tom Becker | Chicago hotel 678.57 + cab | **Reject** | room rate 289/night > 250 |
| EXP-2044 | Grace Ito | client dinner 231.50, 4 attendees | **Reject** | Pinot Noir + 2 beers on receipt (alcohol) |
| EXP-2045 | Ravi Menon | AdTech Summit 450.00 dated 8 Jul, submitted 15 Oct | **Reject** | older than 60 days |
| EXP-2046 | Leo Marsh | NYC hotel 2 × 329 + taxes/fees 762.06, JFK cab | Approve (trap) | NYC limit 350 |
| EXP-2047 | Aisha Bello | dinner 212.00, 4 attendees, no alcohol | Approve (trap) | 53/attendee |
| EXP-2048 | Tom Becker | stock photo plan 19.00, no receipt | Approve (trap) | < $25 |
| EXP-2049 | Grace Ito | car rental 142.60 dated 8 Oct | **Reject** | rental receipt dated 28 Sep |
| EXP-2050 | Ravi Menon | business-class flight 3,840 + London hotel 4 × 338 | Approve (trap) | VP pre-approval PA-2291 on report; London limit 350 |
| EXP-2051 | Leo Marsh | Denver hotel 460.69 (folio 478.69 incl. minibar 18.00, removed) + dinner 41.80 | Approve (trap) | claim < receipt only by the personal item, stated |
| EXP-2052 | Aisha Bello | courier 64.75 | Approve | |

## Ground truth (B)
Lines (amount / category / accepted dates / merchant): Northline Airways 412.80 Airfare (14 Oct, or issue date 2 Oct,
or 16 Oct); Lakeshore Grand Hotel 561.17 Lodging (14–16 Oct; rate 239 ≤ 250); Chicago Yellow Cab 52.35 Ground transport
(14 Oct); Zipp 47.90 Ground transport (16 Oct); Harbor & Vine **186.40** Meals (15 Oct, **4 attendees**). Total
1,260.62, status Submitted, each receipt attached (md5 of the stored blob = md5 of the Downloads file).
CSV: Marketing, Approved, submitted Oct 2026 → seed set {2021, 2023, 2025, 2027, 2030, 2032} plus whatever A had
approved at export time (up to +7: 2041, 2046, 2047, 2048, 2050, 2051, 2052).

## Shared resources and expected contention
- **One cookie session, one active role.** A needs the Approver view the whole time; B must switch to the Employee view
  to create/edit its report and back to the Approver view to export. A switch by one agent changes the view under the
  other: A's next Approve/Reject is refused ("Switch to the Approver view… Your decision was not saved."), B's next
  "Add line" is refused in the Approver view. Non-silent, but an agent that does not read the banner loses work.
- **Remembered Reports filter + export-current-filter.** If A browses the Reports list (e.g. status Submitted) between
  B setting its filter and B clicking Export, B downloads the wrong list (silent).
- **Content dependency:** B's export depends on A's approvals; any consistent snapshot is accepted, so both orders work.
- **Log out** ends the session for both; after logging in again the session starts in the Employee view.
- Same Chrome window: tabs, file-chooser dialog (B) and receipt pop-ups (A) compete for focus.

## Provenance
Manager approval of team expense reports against a T&E policy (receipt matching, per-diem/lodging caps, alcohol,
late submission, business-class pre-approval) is the standard SAP Concur / Expensify / Workday approver workflow;
filing an itemized trip report with receipt uploads and removing alcohol from a dinner is the classic employee-side
chore. Role/delegate mode switching mirrors Concur "Acting as…" and SAP launchpad roles; "export current view" mirrors
list exports in most ERP portals.

## Grading
### A — `evaluate_approve` (db + summary file)
| weight | check |
|---|---|
| 0.04 × 7 | each compliant report Approved by Dana |
| 0.08 × 5 | each violating report Rejected by Dana |
| 0.024 × 5 | reject comment names the problem (per-report regex: amount/184/248…, rate/night/250/289…, alcohol/wine/beer…, 60 days/late/July…, date/28 Sep…) |
| 0.15 | summary file: per report, the line with its number says the expected decision AND it equals the app's state |
| 0.05 × decided fraction | no other report's status changed |
Cap: fewer than 6 of 12 decided → ≤ 0.4.

### B — `evaluate_claim` (db + CSV)
| weight | check |
|---|---|
| 0.08 / 0.02 | best new report by Dana is Submitted / title mentions Chicago and Kestrel |
| 0.50 | 5 expected lines (greedy match): amount, category, date, merchant, receipt md5 (+ attendees = 4 for the dinner), equal share |
| 0.05 | exactly the 5 lines, nothing extra (no wine line, no September lunch) |
| 0.05 | report total = 1,260.62 |
| 0.05 | CSV exists with report numbers |
| 0.20 / 0.10 | CSV rows ⊇ seed-approved Oct Marketing AND ⊆ currently approved Oct Marketing (0.10 if only ⊆) |
| 0.05 | CSV totals equal the app's (only if no out-of-scope rows) |
Cap: no new report by Dana → ≤ 0.3.

## Reference solution (scripted in `lib_wtest_w2.py`)
A: switch to Approver view; for each queued report open the receipts, decide per the table, write a specific reject
comment; write the 12-line summary. B: Employee view → New report → 5 × Add line (multipart upload of the Downloads
file) → Submit; Approver view → Reports with status Approved, month October 2026, department Marketing → Export CSV →
save to ~/Documents/marketing_approved_oct2026.csv.

Expected solo length: A ≈ 60–90 GUI steps (12 reports, ~17 receipts to open and zoom, 12 decisions with typing, policy
PDF, a text file); B ≈ 55–75 steps (5 receipts to view, 5 line forms with 6 fields + file chooser each, submit, role
switch, 3 filters, export, move/rename the download). Human: ~30 and ~25 minutes.

## Self-test (offline, node 0; `lib_wtest.py w2`)
```
[w2] python3.10 smoke test (GET /login): 200
[w2] pristine                     approve=0.0  claim=0.0
[w2] A_only                       approve=1.0  claim=0.0
[w2] B_only                       approve=0.0  claim=1.0
[w2] A_then_B                     approve=1.0  claim=1.0
[w2] B_then_A                     approve=1.0  claim=1.0
[w2] partial_A_rubber_stamp       approve=0.4175  claim=0.0     (approves all 12)
[w2] partial_A_vague              approve=0.73  claim=0.0       (right decisions, vague reject comments, no summary)
[w2] partial_B                    approve=0.0  claim=0.5933     (dinner incl. wine, two taxis without receipt, no export)
[w2] B_unfiltered_export          approve=0.0  claim=0.75       (exports the default list: all Marketing reports)
[w2] role_flip                    approve=0.596  claim=1.0      (B switches to Employee view mid-way; A's last 6 refused)
[w2] sticky_filter_export         approve=1.0  claim=0.75       (A's list filter active when B clicks Export)
[w2] export_midway                approve=1.0  claim=1.0        (B exports after 6 of A's decisions: snapshot accepted)
[w2] logout_hazard                approve=0.4  claim=1.0        (B logs out; A re-logs in, lands in Employee view)
[w2] fuzz_approver                (104 pages, all forms x 13 hostile values: 0 5xx)
[w2] fuzz_employee_draft          (draft editor incl. multipart forms: 0 5xx)
[w2] fuzz                         (generic: 0 5xx)
```
Uploads made with multipart/form-data are stored byte-identical (md5 check passes for PDF, JPG and PNG).

## Known risks
- An agent may script HTTP (curl with cookie jar) — still needs to read every receipt image and the image PDF.
- Date of the lodging line is ambiguous in practice (check-in vs check-out): any night of the stay is accepted; the
  airfare accepts travel or issue date.
- `submitted` of B's new report uses the Guest clock (not graded). Approval timestamps also use the Guest clock; the
  export's month filter is by submission month, which is fixed in the seed for all graded reports.
- The DB path is visible in `ps`; direct sqlite edits would bypass md5-bearing receipt rows (B) only if the agent
  recomputes md5 — unlikely, not prevented.
