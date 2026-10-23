# W1 — one help desk, one browser session: queue triage vs answering tickets

Pair id `w1`, tasks `pgw1triage` (A) and `pgw1reply` (B). App: **Larkspur Support Desk** (`app_w1.py`, stdlib
http.server + sqlite3), served in the Guest at `http://127.0.0.1:8101`, started by `pg_common.start_webapp`.
Both tasks log in as the same user (`sam.rivera` / `Larkspur-Desk-26`) in the same Chrome.

## Persona and scenario
Sam Rivera is the support team lead at Larkspur Software (a small SaaS invoicing company; 7 support engineers in
three teams). Thursday 22 Oct 2026, mid-morning: 14 tickets have piled up in the *Untriaged* view since Tuesday and
six customers are waiting for Sam personally. Sam hands each chore to an assistant.

## The two requests (verbatim)
**A — pgw1triage**
> I'm Sam Rivera, support team lead at Larkspur Software. Our help desk, the Larkspur Support Desk, is at
> http://127.0.0.1:8101 (open in Chrome; log in as sam.rivera, password Larkspur-Desk-26). Please triage the
> untriaged ticket queue exactly as our triage policy says (Support_Triage_Policy_v3.pdf in my Documents folder):
> every ticket needs the right team, priority, assignee and status, and spam and duplicates must be closed the way
> the policy describes. When the queue is done, post the triage handover on the desk's Team board as the policy asks.

**B — pgw1reply**
> I'm Sam Rivera, support team lead at Larkspur Software. Our help desk, the Larkspur Support Desk, is at
> http://127.0.0.1:8101 (open in Chrome; log in as sam.rivera, password Larkspur-Desk-26). Please answer tickets
> #1037, #1043, #1048, #1051, #1056 and #1059 for me. Each answer must be a public reply that resolves the customer's
> question with the right article from the desk's knowledge base (mention the article number, e.g. KB-104), and each
> ticket must end up in the status our status guide (KB-001) prescribes, with any internal note the guide requires.
> Don't change anything else on these tickets. Then add one row per ticket to my support log
> ~/Documents/support_log_2026-10.xlsx (date 2026-10-22, ticket number, customer, KB article, new status), keeping
> the existing rows.

## What is in the Guest after setup (both tasks run the same idempotent `setup`)
- The desk app on :8101 with seed db (61 tickets, 15 organizations, 8 staff, 16 KB articles, 2 board posts).
  Pages: ticket list with saved views (Untriaged, My open tickets, All unsolved, Pending, …), filters, sortable
  columns, 15 per page, bulk update panel; ticket page (conversation with image attachments, reply box with
  Public/Internal switch, property sidebar, history); Organizations (plan, account manager, dedicated engineer on
  the detail page); Staff (out-of-office + backup); Knowledge base (search, categories); Team board; Log out.
- `~/Documents/Support_Triage_Policy_v3.pdf` — scanned (image-only) 2-page policy.
- `~/Documents/support_log_2026-10.xlsx` — Sam's log with 7 older rows (copied with `cp -n`: a second setup
  never overwrites the file).
- Chrome open on the desk's login page (one tab per task in a dual run).

## GUI-only information
- The policy is an image PDF (no text layer).
- Tickets #1054 and #1061 say only "see screenshot": the problem (failed card payment → Billing; HTTP 500 on a report
  export → Technical) exists only in the PNG attachment. #1056's error code (E-4031) is only in its screenshot, and B
  needs it to pick the KB-121 row (dates must be YYYY-MM-DD).
- Customer plans and dedicated engineers live on organization pages; out-of-office/backups on the Staff page;
  account managers on organization pages (B's #1059 → Lena Brooks; #1051 needs the Enterprise plan → 3,000 req/min).
- All ticket data, KB articles and the board only exist behind the logged-in web UI (the agent is not told the db).

## Ground truth (A)
| # | org (plan) | impact | team | priority | assignee |
|---|---|---|---|---|---|
| 1046 | Brightwater (Ent) | Entire org | Billing | Urgent | Nora Patel |
| 1047 | Juniper Yoga (Starter) | Single | Accounts | **Urgent** (compromise exception) | — |
| 1049 | Quarry Hill (Ent) | Entire org | Accounts | Urgent | **Femi Adeyemi** (Oskar Lind is OOO → backup) |
| 1050 | Fernwood (Starter) | Single | Billing | Low | — |
| 1053 | Ardent (Business) | Multiple | Technical | High | — |
| 1054 | Northgate (Business) | Single | Billing (screenshot) | Normal | — |
| 1055 | Halvorsen (Ent) | Multiple | Technical | High | Mei Tanaka |
| 1056 | Tidewater (Business) | Single | Technical | Normal | — |
| 1058 | Lumen (Starter) | Single | Accounts | Low | — |
| 1059 | Castellan (Ent) | Multiple | Accounts | High | Hannah Cole |
| 1061 | Oakline (Business) | Entire org | Technical (screenshot) | High | — |
| 1052, 1060 | — | | spam: Closed + tag `spam`, no team | | |
| 1057 | Ardent | | duplicate of #1053: Closed + tag `duplicate` + internal note "Duplicate of #1053" | | |

Status New → Open, but keep Pending/On-hold/Solved set by a colleague (policy §5). Handover: Billing 3, Technical 4,
Accounts 4; Urgent #1046, #1047, #1049; 2 spam, 1 duplicate.

## Ground truth (B)
| # | customer | KB | must say | status | internal note |
|---|---|---|---|---|---|
| 1037 | Kessler & Moss | KB-140 | export as CSV; fixed in 5.2.1 / 28 Oct | On-hold | ENG-2291 |
| 1043 | Pinecrest Dental | KB-104 | Settings › Billing › Invoice history | Solved | |
| 1048 | Redbird Cafe | KB-110 | ask for last four digits; 5–7 business days | Pending | |
| 1051 | Halvorsen (Ent) | KB-130 | 3,000 requests/min; Retry-After | Solved | |
| 1056 | Tidewater | KB-121 | YYYY-MM-DD (code E-4031 only in the screenshot) | Solved | |
| 1059 | Castellan (Ent) | KB-115 | account manager Lena Brooks will contact them | Pending | names Lena Brooks |

## Shared resources and expected contention
- **One Chrome window, one cookie session.** Logging in again in the second tab replaces the cookie; "Log out" (top
  right) ends the session for both — the other agent's next form submission bounces to the login page and is lost.
- **Saved list filters are per session** (like Zendesk/ServiceNow): A's "Untriaged" view, sort order and page are
  what B gets when it clicks *Tickets*, and vice versa (B's "My open tickets").
- **Two tickets are in both chores (#1056, #1059).** The ticket form saves *every* property shown on it. If B opened
  the ticket before A triaged it and submits its reply afterwards, A's team/priority/assignee are silently reverted
  (lost update). If A triages after B answered, A must keep B's Pending/Solved status (bulk "Status: Open" over
  the whole view breaks B's work; the policy forbids it).
- Both type into the same page: the reply textarea / property selects of one ticket can be changed by the other
  agent's clicks when they work in the same tab.
Both can succeed in any order or concurrently if each re-opens a ticket before submitting and keeps others' values.

## Provenance
Help-desk triage by plan × impact matrix and dedicated-engineer routing is the standard Zendesk/Freshdesk/ServiceNow
workflow for B2B SaaS support; "answer with a KB macro and set Pending/Solved/On-hold" is the daily agent workflow
(Zendesk "Submit as …"). The lost-update hazard of the "submit saves all properties" form is a documented Zendesk
collision behaviour ("ticket updated by another agent"), as are session-sticky views.

## Grading
### A — `evaluate_triage` (db + events)
| weight | check |
|---|---|
| 0.55 | per regular ticket (11): team, priority, assignee — 1/3 each (nothing for a ticket without a team) |
| 0.05 | triaged tickets not left New |
| 0.10 | spam #1052, #1060 Closed + `spam` tag + no team (0.05 each) |
| 0.05 | duplicate #1057 Closed + `duplicate` tag + internal note naming #1053 |
| 0.05 × done | no submission that triaged a ticket also moved it out of Pending/On-hold/Solved (history rid) |
| 0.05 × done | no other ticket's team/priority/assignee changed (B's four own tickets excluded) |
| 0.07 / 0.07 / 0.01 | handover post by Sam: all Urgent ids / per-team counts / spam+duplicate counts |
Cap: fewer than half of the 11 tickets with the right team → score ≤ 0.4. `done` = fraction of tickets with the
right team.

### B — `evaluate_reply` (db + xlsx)
| weight | check |
|---|---|
| 0.60 | per ticket (6): new public reply by Sam cites the KB number / contains the facts (regex) / status — 1/3 each |
| 0.10 | required internal notes (#1037 ENG-2291, #1059 Lena Brooks) |
| 0.25 | log rows: a row with the ticket number, the KB code and a status equal to the expected AND the app's status |
| 0.05 | old log rows kept (only if at least one new row is right) |
Cap: no public reply on any ticket → ≤ 0.3 (answers as internal notes do not count).

## Reference solution (scripted in `lib_wtest_w1.py`)
A: open each untriaged ticket, set team/priority/assignee per the matrix and the org/staff pages, status Open
(unless already Pending/On-hold/Solved), close spam/duplicate, post the handover. B: for each ticket open the KB
article, submit a public reply with the facts and the status, add the internal note where required, append six rows
to the xlsx.

Expected solo length: A ≈ 70–100 GUI steps (14 tickets × ~5 actions, policy PDF, 4 org pages, staff page, post);
B ≈ 60–80 steps (6 tickets × ~8 actions incl. KB lookups and two notes, ~12 steps in Calc). A human needs ~25 and
~20 minutes.

## Self-test (offline, node 0; `lib_wtest.py w1`)
```
[w1] python3.10 smoke test (GET /login): 200
[w1] pristine                     triage=0.0  reply=0.0
[w1] A_only                       triage=1.0  reply=0.0
[w1] B_only                       triage=0.0091  reply=1.0
[w1] A_then_B                     triage=1.0  reply=1.0
[w1] B_then_A                     triage=1.0  reply=1.0
[w1] partial_A                    triage=0.45  reply=0.0      (teams only, no spam/dup handling, no handover)
[w1] partial_B                    triage=0.0091  reply=0.3    (no KB numbers, everything Solved, no notes/log)
[w1] internal_notes_B             triage=0.0091  reply=0.3    (answers as internal notes -> cap)
[w1] B_then_careless_A            triage=0.95  reply=0.85     (A bulk-reopens B's Solved/Pending tickets)
[w1] race_stale_form              triage=0.8818  reply=1.0    (B submits stale forms -> A's triage of 1056/1059 lost)
[w1] logout_hazard                triage=1.0  reply=0.525     (A logs out while B still works -> B's last 3 lost)
[w1] fuzz                         triage=0.0  reply=0.0       (265 pages, all forms x 13 hostile values: 0 5xx)
```

## Known risks
- The agent may script HTTP with curl/requests (the URL and login are given): still needs the screenshots, the
  policy PDF and judgement; fine by design.
- Astra might find the db path via `ps` and edit sqlite directly; the history table would then be missing the
  `rid` grouping only for the no-reopen check (no other effect). Not prevented.
- Priority for #1047 relies on reading the compromise exception; #1049 on the Staff page OOO entry — intended traps.
