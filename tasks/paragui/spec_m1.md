# m1: project mail rules vs. vendor quote comparison (family F2, one Thunderbird)

## Scenario and persona
Sofia Marquez is the office and project coordinator at Larchmont Design Group, a Chicago architecture firm
(`sofia.marquez@larchmontdg.com`). The firm is renovating the Riverside Public Library (project code RLP).

Sofia hands two chores to two assistants at the same time:
- The project director has just issued mail-handling rules for the project.
- The same director wants the reading-room furniture quotes compared and a vendor picked.

Thunderbird 115 runs an offline POP3 profile with 28 messages in the Inbox (built by `build_m1.py`).

## User requests (verbatim)
**pgm1rules (A)**
> Daniel Okoye, our project director, emailed me the new mail-handling rules for the Riverside Library project - they are in the scanned memo attached to his email "Mail rules for the Riverside Library project". Please set this up in my Thunderbird account (sofia.marquez@larchmontdg.com) exactly as the memo says: the folders, the two tags and the four message filters in the given order (the filters must also work on mail that arrives later). Then run the filters on my Inbox so that my existing mail gets sorted. Finally, reply to Daniel's email confirming that it is set up and telling him how many of my existing messages ended up in each of the four project folders. Save the reply as a draft - don't send it.

**pgm1quotes (B)**
> Daniel asked me to sort out the reading-room furniture for the Riverside Library job - his email "[RLP] Reading room furniture - please compare the quotes" has the criteria. Four vendors sent quotes by email: find them in my Thunderbird mailbox and save every quote PDF into ~/Documents/RLP/Quotes/ (keep the file names). Then make a workbook ~/Documents/RLP/Furniture_Quotes.xlsx with one row per vendor and the columns Vendor, Quote No, Total (USD, incl. delivery and tax), Delivery Date, Chair Warranty (years), Meets Criteria (Y/N). If a vendor revised its quote, use only the latest version. Pick the vendor according to Daniel's criteria, then reply to that vendor's latest quote email accepting the quote (mention their quote number and our purchase order number), and reply to Daniel telling him which vendor you chose and the total. Save both replies as drafts; don't send anything.

## Content (hidden facts)
**Memo** (`RLP_Mail_Handling_Memo.pdf`, an image-only scan):
- Folders: `Riverside Library/{Client, Consultants, Invoices}`.
- Tags: `RLP` and `RLP Billing`.
- Filters, first match wins:
  - F1: subject contains "RLP" and "invoice" → tag RLP Billing, star, move to Invoices.
  - F2: sender at riversidelibrary.org → tag RLP, move to Client.
  - F3: sender at kalmarstructural.com or greenfieldmep.com → tag RLP, move to Consultants.
  - F4: "[RLP]" in subject → tag RLP, move to Riverside Library.
- The filters must run on new mail and manually.

**Existing mail after a correct run:**
- Invoices 3, Client 4, Consultants 2, Riverside Library 8.
- 11 messages stay in the Inbox, including traps:
  - "Invoice templates…" (no RLP)
  - "Your Adobe invoice"
  - "[HPK] …" (another project)
  - "Re: Riverside Library - parking permits" (no [RLP] tag)
- The client's "Invoice approval process" goes to Client, because F1 needs "RLP" in the subject.

**Quotes** (40 chairs and 10 tables, 8.25% sales tax):

| Vendor | Quote | Source | Total | Delivery | Chair warranty | Meets criteria |
|---|---|---|---|---|---|---|
| Northline | Q-2291-R1 (revision replaces Q-2291 = $15,490.58) | revision is an image-only signed scan; original is a text PDF | **$13,585.38** | 20 Nov | 5 y | **Y (winner)** |
| Benchmark | BCF-7730 | image-only PDF | $13,206.50 (cheapest) | week of 7 Dec | 7 y | N (late) |
| Studio Lumen | SL-0912 | image-only PDF | $13,287.69 | 24 Nov | 3 y | N (warranty) |
| Ashford & Pike | AP-5521 | HTML table in the mail body, 10% discount | $14,072.50 | 25 Nov | 5 y | Y |

- Daniel's criteria: delivered by 27 Nov 2026, chair warranty of at least 5 years, then the lowest total.
- PO number: PO-RLP-0457 (in Daniel's mail).
- Traps:
  - Using the superseded Q-2291 makes Ashford the winner.
  - Ignoring the criteria makes Benchmark the winner.

## Shared resources and expected contention
- **One Thunderbird main window.** A spends long stretches in the Message Filters window, the filter editor, the Tag dialog and the folder pane. B selects messages, opens PDF attachments (Thunderbird's PDF viewer tab), saves attachments and opens two composer windows.
- **A moves B's working set.** All five vendor e-mails and Daniel's furniture request carry "[RLP]", so A's "Run Now" moves and tags them into `Riverside Library` while B is reading them, saving their attachments or replying to them.
  - B's message list empties under it.
  - "Reply" may target a message that just moved.
  - B has to find the quotes again in another folder.
- **Shared dialogs and keyboard focus.** The filter editor is modal-like. B's composer windows steal focus from A's dialogs, and the reverse.
- **Restarts hurt both.** If either agent restarts Thunderbird (seen in C4), the other loses its dialog, composer or selection.
- **Order independence.** Both orders are legitimate. B's checker finds drafts by In-Reply-To wherever the originals live. A's checker ignores Drafts and does not care whether messages were read.

## GUI-only parts
- **A:** the memo exists only as pixels. The filters, tags and folders are Thunderbird-internal state: filter rules written to `msgFilterRules.dat` while Thunderbird runs are ignored or overwritten, so "Run Now" needs the running app.
- **B:** two of the four quotes, including the decisive Northline revision, exist only as pixels in scanned PDFs.

## Grading
**pgm1rules** (`evaluate_rules`):
- Tags present, from `prefs.js` `mailnews.tags.*.tag`: RLP 0.04, RLP Billing 0.04.
- The 4 folders exist: 0.04.
- Filter behaviour: 0.32. The checker parses `msgFilterRules.dat` and **simulates** the filters, in Thunderbird order, on 8 hidden probe messages (6 project, 2 non-project). Each probe must end in the right folder, with exactly the right RLP tags and the right star state. Non-project probes count only if at least one project probe routes correctly.
- The same probes as a manual run (type includes Manual): 0.04.
- Existing project mail in the right folder: 0.22. A message must be only there, not in the Inbox. Moving non-project mail out of the Inbox costs 0.5 × the moved fraction.
- Moved messages carry the right tags (`X-Mozilla-Keys`, mapped key → name) and star (0x0004): 0.10.
- Reply draft to Daniel exists (In-Reply-To the memo mail, To Daniel): 0.05.
- The reply states the four counts (3/4/2/8): 0.15. Counts are read as the number nearest to "invoice", "client" and "consultant", plus 8 anywhere. Only the user's own text counts; the quoted original is stripped.
- **Cap:** no project probe routed correctly (mail sorted by hand, no working filters) → score ≤ 0.4.

**pgm1quotes** (`evaluate_quotes`):
- The 4 quote PDFs are in `~/Documents/RLP/Quotes/` (md5): 0.12.
- Workbook rows, found by vendor name in any column order:
  - total ±$0.02: 0.16
  - quote number: 0.08
  - delivery date (Benchmark: any day in 7–11 Dec): 0.06
  - warranty: 0.06
  - Meets Y/N: 0.08
  - exactly one row per vendor: 0.04
  - Listing the superseded Northline quote makes the Northline total wrong.
- Draft to the winner (In-Reply-To a Northline mail, To rkim@): 0.10.
- That draft's own text contains Q-2291-R1 and PO-RLP-0457: 0.12.
- Draft to Daniel (In-Reply-To his request): 0.06.
- That draft names Northline and $13,585.38: 0.12.
- **Caps:** no workbook → ≤ 0.4. Any acceptance draft addressed to a non-winning vendor → ≤ 0.5.

## Reference solution and expected effort
**A:**
- open the memo PDF (about 3 steps)
- create 4 folders (about 12)
- create 2 tags (about 8)
- build 4 filters with 1–2 conditions and 2–3 actions each (about 45)
- Run Now on the Inbox (3)
- read the folder counts (4)
- reply draft (8)

About **80 GUI steps**; 25–35 minutes for a person.

**B:**
- open 5 vendor mails and their PDFs (about 15)
- save 4 PDFs (about 12)
- build the workbook in LibreOffice Calc with 6 columns and 4 rows (about 30)
- two reply drafts (about 16)

About **70 steps**; 25–35 minutes.

## Provenance
- **A** is the standard "set up mail rules for a new project" request from office IT and PMO memos. Thunderbird's own documentation workflow covers this: Message Filters, Tags, Run Now.
- **B** is the everyday procurement "three-quote" comparison, with the classic pitfalls of a revised quote, a cheapest-but-late vendor and a warranty rule.

## Self-test (offline, simulated Guest; `lib_m1test.py`)
| Case | Score |
|---|---|
| Pristine: rules / quotes | 0.000 / 0.000 |
| A then B: rules / quotes | 1.000 / 1.000 |
| B then A: quotes / rules | 1.000 / 1.000 |
| Partial A: invoice rule placed last | 0.842 |
| Partial A: sorted by hand without filters | 0.400 |
| Partial A: filters only, not run, no reply | 0.480 |
| Partial B: superseded quote, so picks Ashford | 0.500 |
| Partial B: cheapest late vendor, no PDFs saved | 0.500 |

## Known risks
- The checker reads tags from `X-Mozilla-Keys` in the mbox. Thunderbird rewrites that header in place: there is 80-character padding in our mbox files, and Thunderbird's own source code confirms the in-place rewrite. If an agent tags a message in a way that overflows the padding (more than 80 characters of keywords), the tag lives only in the `.msf` index. That is unlikely with two tags.
- If the agent creates the filters on "Local Folders" instead of the account, they are still evaluated (fallback), but they would not run on the account's new mail in reality.
