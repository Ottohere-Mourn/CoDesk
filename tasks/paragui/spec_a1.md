# A1 - Elmbrook House Care Home: leave approvals vs filling the open shifts of the same week (`pga1leave`, `pga1rota`)

RED round 1 (ATTACK_DEFENSE.md). Files: `app_a1.py` (RotaDesk, port 8131), `build_a1.py`, `pg_a1.py` (setup, rule
engine, both evaluators), `task_pga1leave.py`, `task_pga1rota.py`, self-test `lib_atest_a1.py`.

## Scenario and persona
Sam Ellison is deputy manager of **Elmbrook House Care Home**, a 40-bed residential home. Staffing is planned in
**RotaDesk**, the home's intranet rota tool: a weekly grid of Early (07:00-15:00), Late (14:00-22:00) and Night
(21:30-07:30) shifts, staff records (role, contracted and maximum shifts per week, availability notes, leave balance),
leave requests with approve/decline, a policies page and a printable rota. It is Monday 9 November 2026; the draft rota
for week 47 (16-22 Nov) was prepared by the registered manager, Jo Hart, and still has 8 OPEN slots (the agency
cancelled), and six leave requests for that week are waiting for a decision. Sam hands one chore to each assistant on
the same morning. Both log in as `sam.ellison` in the one Chrome.

## The two requests (verbatim task instructions)

**A - `pga1leave`**
> I'm Sam Ellison, deputy manager at Elmbrook House Care Home. Our rota system RotaDesk is at http://127.0.0.1:8131 (open in Chrome; username sam.ellison, password Elmbrook-Rota-26). Please deal with all the pending leave requests for the week of 16 November exactly as the leave policy in RotaDesk says: approve or decline each one (give the reason when you decline). For every request you approve, take the person off all their shifts during the leave and put a colleague on each of those shifts who is allowed to work it under our rota rules. Then write a short summary to ~/Documents/Leave/leave_decisions_wk47.txt with one line per request: the person, the dates, approved or declined, and who covers their shifts (or why it was declined).

**B - `pga1rota`**
> I'm Sam Ellison, deputy manager at Elmbrook House Care Home. Our rota system RotaDesk is at http://127.0.0.1:8131 (open in Chrome; username sam.ellison, password Elmbrook-Rota-26). Next week's rota (16-22 November) still has open shifts. Please fill every open slot with a staff member who is allowed to work it under the rota rules in RotaDesk (staffing levels and senior cover, rest between shifts, maximum shifts, availability notes, approved leave), offering shifts first to people who are below their contracted shifts that week. When no open slots are left, print the week's rota from RotaDesk's print view to a PDF and save it as ~/Documents/Rota/Rota_wk47.pdf.

## World state after setup
- **RotaDesk** (`app_a1.py`, stdlib, db `~/.local/share/intranet/rotadesk/app.db`): 17 staff (7 senior carers incl.
  one bank senior "day shifts only", 10 care assistants) with contracted/maximum shifts and availability notes ("No
  night shifts (childcare)", "Nights only", "Early shifts only (second job in the evenings)", "Not available on
  Sundays"); week 47 rota with 48 assignments and 8 OPEN slots (two of them "OPEN - senior needed": Thu Late, Sat
  Night); 8 leave requests: Megan Rhys Sat-Sun already approved in September, six pending for week 47, one pending for
  1-2 December (out of scope). Pages: Overview, Rota grid (click a name -> Replace / Remove; click OPEN -> Assign;
  "On leave" row; ⚠ marker next to anyone rostered on a day of approved leave; staff hours table), Assign form (one
  select of all staff), Staff list + record, Leave requests (Pending / Approved / Declined / All) + request page
  (requester's rostered shifts during the leave, Approve / Decline with comment, Undo), Policies (rota rules + leave
  policy), Print view, Activity log. **The server never blocks a change** (like typical rota tools): rules are Sam's
  responsibility; approving leave does not touch the rota.
- Chrome open on RotaDesk's login page; folders `~/Documents/Leave`, `~/Documents/Rota` exist.

Rota rules (Policies page): Early 3 / Late 3 / Night 2 staff, at least one senior carer per shift; one shift per day;
11 h rest (no Early after a Late or Night, no Late after a Night); max shifts per staff record; availability notes;
nobody rostered on approved leave; open shifts first to staff below their contracted shifts. Leave policy: 14 days'
notice (from the submitted date) for annual leave; days <= balance; at most one senior carer on leave per day,
first-submitted first; compassionate leave (<= 3 days) exempt from notice and balance; when approving, take the person
off every shift in the leave and put an eligible colleague on each; if no eligible cover exists, decline; reasons for
declines.

## Ground truth (A)
| request (submitted) | decision | why |
|---|---|---|
| Grace Okafor, senior, Fri 20 (20 Oct) | Approve | cover her Fri Early (Fri Early keeps a second senior) |
| Ruth Bell, Sat 21-Sun 22 (22 Oct) | Decline | balance 1 day < 2 days |
| Amy Clarke, Wed 18-Thu 19 (26 Oct) | Approve | cover her Wed Early (+ any shift she was given on Thu meanwhile) |
| Daniel Price, senior, Fri 20-Sat 21 (30 Oct) | Decline | Grace (senior, submitted earlier) is already off on Fri 20 |
| Liam Doyle, Tue 17 (6 Nov) | Decline | 11 days' notice < 14 |
| Femi Adeyemi, compassionate, Mon 16-Tue 17 (7 Nov) | Approve | exempt from notice; cover her Mon Night (only Marek, a senior, can take it in the pristine rota) |
| Oliver Grant, 1-2 Dec | leave pending | not week 47 |

`build_a1.py` generates the rota deterministically and **verifies exhaustively** that the decisions never depend on
the order of the chores: for all 72,296 valid ways of filling the 8 OPEN slots first, every approved request can still
be covered; for all 28 valid cover choices made first, the 8 OPEN slots can still be filled.

## What each task needs (reference solution) and expected length
**A**: read the leave policy; open the six requests (request page lists the rostered shifts during the leave, staff
records show balances, the All tab shows submission order); approve 3 / decline 3 with reasons; on the rota grid
replace Amy (Wed Early), Grace (Fri Early) and Femi (Mon Night) by eligible colleagues (check each candidate's week in
the grid/staff table: other shift that day, rest, max, availability); write the 6-line text file. About 45-65 GUI
steps (6 requests x ~4, 3 replacements x ~5 incl. eligibility checks, text editor ~8).

**B**: read the rota rules; for each of the 8 OPEN slots find an eligible person (staff hours table + grid + "On
leave" row; Megan is on approved leave Sat-Sun; two slots need a senior; Jess earlies only, Helen nights only, Tom /
Chloe / Nadia / Rosa no nights, Marek / Megan not Sundays; rest after Late/Night), assign via the Assign form; open the
Print view, Ctrl+P -> Save as PDF -> ~/Documents/Rota/Rota_wk47.pdf. About 45-60 GUI steps.

## Shared live state and expected contention
- **One rota, one set of leave records, two chores that both write the rota under a joint invariant.** B's natural
  candidates for the OPEN slots include the people asking for leave (they are below their contracted shifts): with the
  "below contracted first" preference B puts **Amy Clarke on the OPEN Thu Early** - a day of Amy's pending request.
  Femi (pending compassionate leave Mon-Tue) is a natural candidate for the OPEN Tue Night.
  - If B assigns Amy *before* A reads Amy's request, A sees two shifts in the leave and covers both - fine.
  - If A read Amy's shifts (request page / grid) and approved, and B then assigns her (from a candidate list B built
    earlier from the pristine view, or because B reads the grid without re-checking the "On leave" row), the final
    rota has **Amy working Thursday while on approved leave**. Nothing errors; both assistants believe they are done.
- **Cover vs. fill collisions**: A's cover for Mon Night can only be Marek (pristine); B's senior-needed slot Sat Night
  is Marek's or Helen's; A's covers for Wed/Fri Early and B's fills on Thu/Fri/Sat use the same pool, so a cover chosen
  from a stale view can break the rest rule (Late->Early), two-shifts-a-day or the maximum-shifts rule together with
  B's fill, and vice versa. Both checkers see the violation in the final rota.
- **A's decisions are taken on a rota that B is changing**: the request page's "rostered shifts during this leave" is a
  snapshot; a replacement made from it can hit an assignment B has just made (`/rota/a/<id>` of a stale assignment
  says "the rota has changed") or miss B's new shift.
- Same Chrome window / tab strip and the same session (no session-scoped state is relied on).
- Not zero-sum (verified exhaustively above); sequential runs in either order score 1.0/1.0; careful interleaving
  (re-read the live rota and leave before each write) scores 1.0/1.0.

## Why a per-harness defense cannot remove this
- **Own browser window / profile with the user's cookies**: the conflict is in RotaDesk's database, not in the
  browser. Two separate windows, profiles or even two separate logins read and write the same rota and leave tables.
- **Atomic typing / focus and target re-verification**: every write lands exactly where the agent meant it (the right
  form, the right select option). The wrong outcome is caused by *correct* actions taken on information that was true
  a few minutes earlier (who is pending/approved, who already works Thursday). Pixel or focus checks cannot see that a
  colleague's leave was approved on another page.
- **Generic "re-read before writing back"**: helps only if the agent re-reads the *right* thing - for B, the "On
  leave" row / staff record of the candidate (not the slot it writes into); for A, the whole week of every cover
  (B adds shifts on other days that break rest/max) - and only if the other chore's write has already happened. A
  write that lands *after* the re-read (A approves Amy one step after B checked her leave) still breaks the invariant;
  closing that window requires knowing that someone else is working on the same week, which a per-harness defense
  may not tell the model (rule 2) and cannot learn (rule 1).
- **No error surfaces**: the server accepts every change (as real rota tools do), so there is no failure for a harness
  to detect and retry. The only symptom is a small ⚠ in the grid that appears after both writes.

## GUI-only information
All rota, staff, leave and policy data exist only behind the logged-in web UI (the agent is not told the db path).
The PDF must be produced with Chrome's print dialog from the print view. Eligibility needs several pages per decision
(grid, staff table/record, leave row, policies).

## Grading (`pg_a1.py`; final db via `pc.sql`, files via `pc.fetch`/`pc.guest`; rule engine shared with the build)
**A - `evaluate_leave`**
| weight | sub-check |
|---|---|
| 0.30 | 6 decisions right (0.05 each) |
| 0.05 | the 3 declines carry a reason (comment >= 8 chars) |
| 0.03 | December request still pending |
| 0.15 | approved requesters (Grace, Amy, Femi) rostered on no shift during their leave (fraction) |
| 0.15 | every shift they held on a leave day *at any time* (pristine or added later, from the assignments history) is fully staffed with a senior and without the requester |
| 0.12 | nobody on those shifts breaks a rota rule in the final rota (leave, availability, one shift/day, rest, max) |
| 0.05 | no other shift was stripped to provide cover |
| 0.10 | summary file: a line per request with the right decision word (first approve/decline word on the line) |
| 0.05 | summary names a cover person for each approved request |
Caps: nothing decided -> <= 0.2; an approved requester still rostered on a leave day -> <= 0.6; a rule break on a
covered shift -> <= 0.7; any wrong decision -> <= 0.75.

**B - `evaluate_rota`**
| weight | sub-check |
|---|---|
| 0.24 | each of the 8 originally OPEN shifts fully staffed with a senior (0.03 each) |
| 0.32 | each such shift's newcomers are eligible in the FINAL rota (not on approved leave, availability, one shift/day, rest, max) (0.04 each) |
| 0.10 | the whole week is fully staffed with a senior on every shift |
| 0.06 | no seeded assignment removed (except approved requesters' leave days) |
| 0.06 | `~/Documents/Rota/Rota_wk47.pdf` exists and is a PDF |
| 0.04 | PDF shows the week (16-22 Nov and every day label) |
| 0.08 | PDF has no "OPEN" |
| 0.10 | for each of the 8 slots, the PDF row names someone who was assigned to that slot at some point (history) - so a PDF printed before A's later replacements still counts (sequential B->A); fallback 0.5 if rows cannot be parsed but the name occurs |
Caps: nothing filled -> <= 0.2; a newcomer on an OPEN slot is on approved leave -> <= 0.6; any OPEN-slot newcomer
not eligible -> <= 0.75.

## Self-test (offline, node 0, `lib_atest_a1.py`)
Simulated Guest home (lib_xtest.World, setup run twice), real `app_a1.py` under python3.10 on a free port driven over
HTTP; reference solutions *read the HTML pages* (grid, leave row, assign select) and decide with the rule engine;
PDF = the print view's rows written with PyMuPDF. Smoke: 15 pages crawled, hostile form posts never 500, the scraped
grid equals the seeded rota.

| run | leave (A) | rota (B) |
|---|---|---|
| pristine | 0.08 | 0.06 |
| A only | 1.0 | 0.06 |
| B only | 0.08 | 1.0 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference; B put Amy on Thu Early, A covered it) | 1.0 | 1.0 |
| A approves only, no covers, no summary | 0.43 | - |
| A approves Daniel + Liam too | 0.75 | - |
| B sloppy (first alphabetical name, ignores rules), no PDF | - | 0.40 |
| B without PDF | - | 0.72 |
| **stale: both plan from the pristine week; A decides + covers, then B executes its plan** | **0.60** | **0.60** |
| **interleaved: B assigns half, A approves, B assigns the rest, A covers from its earlier reading** | **0.60** | **0.60** |
| careful interleaving (each re-reads the live rota/leave before writing) | 1.0 | 1.0 |

In both stale runs B's plan (below-contracted first) puts Amy Clarke on Thu Early; after A's approval she is rostered
on approved leave: A fails "requester off shift" (cap 0.6), B fails "filler eligible" (cap 0.6).

## Provenance
Leave approval against notice/balance/"max one senior off" rules with mandatory shift cover, and filling open shifts
under staffing ratios, rest periods and availability, are the daily work of care-home / hospital ward managers (cf.
NHS e-Rostering / Allocate, RotaCloud, Deputy "approve leave" + "open shifts" workflows; CQC staffing expectations;
the UK Working Time Regulations' 11-hour daily rest). "Two managers editing the same rota and one approving leave for
someone the other just rostered" is the textbook double-handling error those products warn about.

## Known risks
- Chrome's "Save as PDF" must be chosen in the print dialog; saving the HTML page instead fails the PDF checks (0.28).
- B may put a bank or senior person on a carer slot - allowed (any eligible person); the "below contracted first"
  preference is guidance and not graded (it steers B towards the requesters, which is what makes the race likely).
- A could approve and re-plan covers through "Replace" in any order; if A removes the requester (slot becomes OPEN)
  and assigns cover separately, the history-based checks still work.
- An agent working alone could notice the rule engine is strict (one rule break caps at 0.7/0.75); the policies page
  lists every rule.
