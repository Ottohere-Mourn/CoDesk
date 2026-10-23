# W4 — one ATS, one browser session, one set of interviewer calendars: feedback decisions vs interview scheduling

Pair id `w4`, tasks `pgw4feedback` (A) and `pgw4schedule` (B). App: **Quillon Talent** (`app_w4.py`, stdlib
http.server + sqlite3), served in the Guest at `http://127.0.0.1:8104`, started by `pg_common.start_webapp`.
Both tasks log in as the same user (`jordan.ellis` / `Quillon-Talent-26`) in the same Chrome.

## Persona and scenario
Jordan Ellis is the talent acquisition lead at Quillon Health (health-tech, ~400 people). Friday 23 Oct 2026: the
paper feedback forms from this week's phone interviews have been scanned into the ATS, and the hiring manager for
two engineering roles, Priya Raman (Director of Engineering), has limited interview time next week and is at a
conference on Friday. Jordan gives the decisions to one assistant and the scheduling + weekly report to another.

## The two requests (verbatim)
**A — pgw4feedback**
> I'm Jordan Ellis, talent acquisition lead at Quillon Health. Our applicant tracking system, Quillon Talent, is at
> http://127.0.0.1:8104 (open in Chrome; log in as jordan.ellis, password Quillon-Talent-26). The phone-interview
> feedback forms of the eight candidates in the stage "Interviewed - awaiting decision" have been scanned and attached
> to their profiles. For each of them, enter the scorecard in Quillon Talent exactly as written on the form and move
> the candidate to the stage that our interview decision rubric (Interview_Decision_Rubric.pdf in my Documents folder)
> prescribes. Book the onsite loop for next week (26-30 Oct 2026) for everyone who goes to Onsite, as the rubric and
> the requisition's interview plan describe. Finally, leave a note on each of the two requisitions saying who goes to
> onsite (with the date), who goes to hiring manager review and who was rejected.

**B — pgw4schedule**
> I'm Jordan Ellis, talent acquisition lead at Quillon Health. Our applicant tracking system, Quillon Talent, is at
> http://127.0.0.1:8104 (open in Chrome; log in as jordan.ellis, password Quillon-Talent-26). Please schedule the
> hiring manager interviews for the five shortlisted Staff Data Engineer candidates (REQ-221): Nadia Rahman, Owen
> Fischer, Keiko Sato, Luis Ortega and Grace Mwangi. Each one is a 45-minute "Hiring manager interview" with Priya
> Raman next week (26-30 Oct 2026). Book them in the Quillon Talent calendar inside Priya's interview availability,
> respecting each candidate's availability note on their profile and without double-booking Priya, and move each
> candidate to the stage "HM interview". Then create my weekly recruiting summary
> ~/Documents/recruiting_weekly_wk43.xlsx with two sheets: "Applications", with the number of applications received
> from 19 to 23 Oct 2026 per requisition (one row per requisition code) and per source (one column per source), as
> shown on the Reports page; and "HM interviews", listing the five interviews (candidate, date, start time,
> interviewer).

## What is in the Guest after setup (idempotent `setup`, run by both tasks)
- Quillon Talent on :8104 with seed db: 6 requisitions (with interview plans), 82 candidates, 10 interviewers with
  weekly availability windows and out-of-office days, 29 interviews (13 next week), 10 scanned feedback forms.
  Pages: Candidates (saved views, search, filters by requisition/stage/recruiter, sortable, 20 per page, filters kept
  in the session), candidate page (profile incl. availability note, attachments shown inline, scorecards + "Add
  scorecard" form, interviews, notes, history, status box Stage/Rejection reason/Recruiter saved as one form),
  Requisitions (interview plan, notes for the hiring team), Interviewers (weekly availability + OOO), Interview
  calendar (week grid for one interviewer, availability shaded, week/person kept in the session, list of all
  interviews of the week; booking form with candidate, type, date, start, duration, interviewer checkboxes —
  conflicts are only warned about, like Google Calendar; edit/cancel), Reports (applications by requisition × source
  for a date range; current pipeline), Log out.
- `~/Documents/Interview_Decision_Rubric.pdf` — scanned (image-only) one-page rubric (`cp -n`, never overwritten).
- Chrome open on the login page.

## GUI-only information
- The eight feedback forms are PNG scans (hand-marked X boxes for four 1–5 ratings, a ticked recommendation,
  interviewer name, handwritten-style comments, slight rotation/noise) — the ratings exist only as pixels.
- The rubric is an image PDF. Interview plans, availability windows, OOO days, existing bookings, candidates'
  availability notes and the applications report are only reachable through the logged-in web UI.

## Ground truth
A (rubric: No hire → Rejected; avg ≥ 3.5 → Onsite; avg < 2.5 → Rejected; else Hiring manager review; reason
"Did not pass interview"):

| candidate | req | form (interviewer: ratings, rec) | avg | stage | onsite constraint |
|---|---|---|---|---|---|
| Ethan Brooks | 214 | Tomas Novak: 4 4 3 4, Hire | 3.75 | Onsite | flexible |
| Mariam Haddad | 214 | Aisha Bello: 5 4 4 5, Strong hire | 4.5 | Onsite | not Tue 27 Oct |
| Lucas Meyer | 214 | Kenji Watanabe: 4 4 4 3, **No hire** | 3.75 | Rejected (rule 1 trap) | |
| Chloe Dubois | 214 | Tomas Novak: 3 3 4 3, **Strong hire** | 3.25 | Hiring manager review | |
| Victor Lindqvist | 214 | Aisha Bello: 2 2 3 2, Hire | 2.25 | Rejected | |
| Amara Okafor | 216 | Samuel Osei: 4 3 4 4, Hire | 3.75 | Onsite | afternoons only |
| Daniel Kim | 216 | Samuel Osei: 3 2 3 3, Hire | 2.75 | Hiring manager review | |
| Sofia Marin | 216 | Helen Park: 2 3 2 2, No hire | 2.25 | Rejected | |

Onsite loops: REQ-214 = one 90-min "Onsite loop" with Priya Raman + exactly one of Tomas Novak / Aisha Bello /
Kenji Watanabe; REQ-216 = one 60-min "Onsite loop" with Helen Park + Samuel Osei. Inside every panelist's weekly
availability, not on an OOO day (Priya: Fri 30 Oct), no overlap with any other interview of any panelist.

B: five 45-min "Hiring manager interview"s with exactly Priya Raman, next week, inside her availability (not Friday),
no overlap, respecting: Nadia — must finish by 12:00; Owen — not Monday; Keiko — Wed/Thu only; Luis — start ≥ 13:00;
Grace — any. Stage "HM interview". Applications 19–23 Oct: per requisition × source counts from the db (6 × 5
cells; A never changes them).

## Shared resources and expected contention
- **Priya Raman's calendar** is needed by both: A's two REQ-214 onsites (2 × 90 min) and B's five interviews
  (5 × 45 min) must fit into ~13 h of free availability (Mon 9–12 & 14–17, Tue 10:30–12, Wed 13–14:30 & 15:15–17,
  Thu 9–11:30). Run one after the other, the second agent sees the first one's bookings and there is enough slack
  (verified for greedy earliest-slot solutions in both orders). Run simultaneously, both read the same free slots
  (Mon 09:00 is the earliest for both Ethan's onsite and Nadia's/Grace's interviews) and double-book Priya; the app
  only shows a warning after saving, so the agent that booked second must notice and move its interview. Each
  checker blames a double-booking on the booking that was saved later (seed bookings count as earliest; then the
  interview's last-save time, then id): that booking loses its "no overlap" points and the task is capped at 0.7.
- **One Chrome window, one cookie session**: "Log out" ends both sessions; a booking form submitted afterwards bounces
  to the login page and is lost. Logging in again in the other tab replaces the session (and its saved state).
- **Session-sticky state**: the candidate list filters/view and the calendar's week and interviewer are stored in the
  session — A filtering on "Awaiting decision" changes what B sees on *Candidates*; B switching the calendar to
  another week/person changes A's grid (A may then read the wrong week's availability).
- The candidate status box saves Stage, Rejection reason and Recruiter together (lost-update hazard if both have
  the same candidate open, e.g. when A looks at REQ-221 candidates while checking Priya's calendar).

## Provenance
Scorecard entry from paper/scanned interview feedback and rubric-based stage moves are standard recruiting
coordinator work in Greenhouse/Lever/Workday; scheduling panel interviews against interviewers' availability and
candidate constraints (and avoiding double-booking a hiring manager shared by several requisitions) is the most
common coordinator request; the "weekly recruiting summary" from the ATS source report into Excel is a typical
Friday reporting chore.

## Grading
### A — `evaluate_feedback`
| weight | check |
|---|---|
| 0.28 | per candidate (8): latest new scorecard has the form's interviewer, four ratings and recommendation |
| 0.30 | per candidate (8): stage correct (and reason "Did not pass interview" for Rejected) |
| 0.30 | per onsite candidate (3): latest new "Onsite loop": week + length + panel exactly per plan 0.4, inside all panelists' availability/not OOO 0.2, does not overlap an earlier-saved interview of a panelist 0.25, candidate's availability note 0.15; ×0.5 if booked more than once |
| 0.04 × done | no onsite booked for candidates that should not go to onsite |
| 0.08 | a new note on REQ-214 and on REQ-216 naming all its candidates and the words onsite / review / reject |
Caps: fewer than half of the candidates in the right stage → ≤ 0.4; any own booking that created a double-booking
(overlaps an interview of the same panelist saved earlier) → ≤ 0.7. (`done` = fraction of stages right.)

### B — `evaluate_schedule`
| weight | check |
|---|---|
| 0.55 | per candidate (5): latest new "Hiring manager interview" next week, 45 min, panel = {Priya} 0.3; inside her availability/not OOO 0.2; does not overlap an earlier-saved interview 0.25; candidate note respected 0.15; stage "HM interview" 0.1 (×0.5 for multiple bookings) |
| 0.25 | xlsx: best sheet with a source header row: per requisition × source cell equals the report (30 cells) |
| 0.20 | xlsx: a row per candidate whose date and start time equal the booking in the app (date/time formats tolerant) |
Caps: no hiring-manager interview booked → ≤ 0.3; any own booking that created a double-booking of Priya → ≤ 0.7.

## Reference solution (scripted in `lib_wtest_w4.py`)
A: for each candidate post the scorecard from the ground-truth form, apply the rubric, set the stage, then book each
onsite in the earliest slot where every panelist is available and free (calendar as stored), then post the two
requisition notes. B: book each candidate's interview in Priya's earliest free slot that satisfies the candidate's
note, set the stage, read the Reports page for 2026-10-19..23 and write the two-sheet workbook.

Expected solo length: A ≈ 80–110 GUI steps (8 scans read + 8 scorecards × ~8 selects, 8 stage saves, rubric,
2–3 calendar look-ups and 3 bookings × ~10 fields, 2 notes); B ≈ 60–80 steps (5 profile notes, calendar for Priya,
5 bookings × ~9 fields, 5 stage saves, report, ~20 steps in Calc). A human needs ~35 and ~30 minutes.

## Self-test (offline, node 0; `lib_wtest.py w4`)
```
[w4] python3.10 smoke test (GET /login): 200
[w4] pristine                     feedback=0.0  schedule=0.0
[w4] A_only                       feedback=1.0  schedule=0.0
[w4] B_only                       feedback=0.0  schedule=1.0
[w4] A_then_B                     feedback=1.0  schedule=1.0
[w4] B_then_A                     feedback=1.0  schedule=1.0
[w4] partial_A                    feedback=0.62  schedule=0.0    (scorecards + stages, no onsite bookings, no notes)
[w4] misread_A                    feedback=0.7  schedule=0.0     (Chloe's 3 read as 4 -> wrong onsite; all onsites on Priya's OOO Friday, clashing)
[w4] partial_B                    feedback=0.0  schedule=0.5005  (ignores candidates' availability notes, no workbook)
[w4] race_same_slot               feedback=0.7  schedule=1.0     (both read the pristine calendar; B saves first, A's onsite then double-books Priya Mon 09:00 -> A capped)
[w4] logout_hazard                feedback=1.0  schedule=0.55    (A logs out while B books -> B's last 3 bookings + stage moves lost)
[w4] fuzz                         feedback=0.0  schedule=0.0     (350 pages, 10 forms x 13 hostile values: 0 5xx)
```
In A_then_B the reference A booked Ethan Mon 09:00 (Priya+Tomas), Mariam Mon 14:00 (Priya+Tomas), Amara Thu 14:00;
B then got Mon 10:30/11:15/15:30, Tue 10:30, Wed 13:00. In B_then_A, B took Mon 09:00/09:45/14:00, Tue 10:30,
Wed 13:00 and A still found Mon 14:45 (Priya+Kenji) and Wed 15:15 (Priya+Aisha).

## Known risks
- Capacity is ample for natural (packed, earliest-first) schedules in either order, but an adversarially scattered
  B schedule could in principle fragment Priya's free time so that two 90-minute onsites no longer fit.
- The calendar grid has 30-minute rows; 15-minute gaps (e.g. Wed 15:15) are only visible in the list below the grid
  / the warning after saving — intended realism, but it makes manual slot finding harder.
- `app_w4.py` is ~860 lines (slightly above the ~800 guideline) because of the calendar grid and booking validation.
- Agents may script HTTP (URL + login given); scorecard values still require reading the scans.
