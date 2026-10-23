# X2 - Recruiting at a data consultancy (`pgx2screen`, `pgx2sched`)

Family F6 (cross-application workflows). Files: `build_x2.py`, `app_x2.py`, `pg_x2.py`, `task_pgx2screen.py`,
`task_pgx2sched.py`, `lib_xtest_x2.py` (offline self-test); shared helpers `lib_x.py`, `pg_xcommon.py`, `lib_xtest.py`.

## Scenario and persona

Alex Moreno is the talent coordinator of **Fernleaf Analytics**, a 60-person data consultancy in Leeds. Hiring runs in
**HireDesk**, the company's applicant tracking intranet (requisitions, candidates, applications with a screening
scorecard and stages, interview slots with video links). It is Friday 30 October 2026 and two hiring managers are
waiting on Alex:

- Grace Liu (Data Analyst, REQ-031) is on a client project and asked Alex to screen the CVs that came in by email,
  using her rubric and tracker.
- Ben Okoro (Product Designer, REQ-027) wants next week's panel interviews booked and the candidates invited.

Alex gives one chore to each assistant. Both run on Alex's desktop: one Thunderbird (alex.moreno@fernleaf.io, offline
POP profile), one Chrome with HireDesk (both log in as `alex`), LibreOffice Calc.

## The two requests (verbatim task instructions)

**A - `pgx2screen`**
> I'm covering the CV screening for Grace Liu's Data Analyst opening (REQ-031). Her email 'REQ-031 screening - rubric
> and tracker' in Thunderbird has the scoring rubric and her tracker, and the applications came in by email with the
> CVs attached (some are scans, and one applicant sent an updated CV). Put every applicant into HireDesk
> (http://127.0.0.1:8122, username alex, password Fernleaf!Talent) on REQ-031 - some people are already on file from
> earlier applications, so don't create duplicates - fill in their scorecard and move them to Phone screen or Rejected
> (with a reason) as the rubric says. Then add them to Grace's tracker, save it as
> ~/Documents/Recruiting/REQ-031_screening.xlsx and reply to Grace's email with the tracker attached, naming the
> shortlisted candidates. Leave the reply in Drafts - don't send it.

**B - `pgx2sched`**
> Please schedule the panel interviews for our Product Designer role (REQ-027). The candidates have answered my
> 'Interview availability' emails in Thunderbird, and Ben Okoro's email 'PD panel interviews next week' has the panel's
> constraints, his booking rule and the panel sheet. Book the slots in HireDesk (http://127.0.0.1:8122, username alex,
> password Fernleaf!Talent) and update anyone who has dropped out, fill in Ben's panel sheet and save it as
> ~/Documents/Recruiting/ProductDesigner_interviews.xlsx, and reply to each scheduled candidate's latest email with an
> invitation giving the date, time and the video link from HireDesk. Leave the replies in Drafts - don't send them.

## World state after setup

- **HireDesk** (`app_x2.py`, port 8122, db `~/.local/share/intranet/hiredesk/app.db`): 5 requisitions (REQ-022 and
  REQ-024 filled, REQ-027 / REQ-029 / REQ-031 open), 25 candidates, 26 applications, 11 interview slots (8 for REQ-027
  with the panel Ben Okoro + Ines Duarte, one already booked for Dan Price on Thu 5 Nov 15:00; 3 for REQ-029).
  Header **requisition selector** stored in the login session, initialised from the user's last requisition
  (REQ-029); it scopes the Pipeline and Interviews pages and **pre-selects the requisition in the "New candidate" and
  "Add to requisition" forms**. Pipeline filters (stage, search, page) are per session too. New-candidate form refuses
  a duplicate email ("open their profile and use Add to requisition"). Application page: scorecard (SQL 0-2, Python/R,
  BI tool, quantitative degree, right to work) with computed total, stage form (reason required for Rejected). Slot
  page shows the video link (only place it exists) and a booking form; booking sets the stage to "Interview
  scheduled"; a candidate can hold only one slot; Rejected/Withdrawn frees a slot. Activity log.
- **Thunderbird** Inbox (17 mails), interleaved over 19-30 Oct: six application mails with CVs (Priyanka Desai and
  Lucia Romero - text PDFs; Tom Fairbairn and Hannah Boateng - scanned image-only PDFs; Daniel Okafor - text PDF, then
  a reply "please use this updated version" with a scanned CV), Grace's rubric with `REQ-031_screening_tracker.xlsx`,
  five availability replies (Chen Wei; Amara Nwosu twice - the later one cancels Wednesday; Leo Fischer; Sofia Marín
  withdrawing), Ben's constraints with `PD_panel_schedule.xlsx`, plus LinkedIn, newsletter, IT and a colleague's mail.
  Sent: Alex's four "Interview availability" mails of 23 Oct (the candidates' replies thread under them).
- Chrome: tab on HireDesk's login page; folder ~/Documents/Recruiting exists.

## What each task needs (the reference solution)

**A** (ground truth): read Grace's rubric; open six CVs (three are scans that must be read visually); score

| applicant | SQL | Py/R | BI | degree | RTW | total | decision |
|---|---|---|---|---|---|---|---|
| Priyanka Desai (text) | 2 (4 yrs) | 1 | 1 Tableau | 1 BSc Maths | Yes | 5 | Phone screen |
| Tom Fairbairn (scan) | 1 (2 yrs) | 1 (R) | 0 (Excel/Power Query is not BI) | 0 (History) | Yes | 2 | Rejected - below threshold |
| Lucia Romero (text) | 2 | 1 | 1 Power BI | 1 MSc Econ | **No** (needs sponsorship) | 5 | Rejected - no right to work |
| Daniel Okafor (updated scan) | 2 (3 yrs; first CV said 1) | 0 | 1 Looker | 1 BEng | Yes | 4 | Phone screen (first CV: 3 -> Rejected) |
| Hannah Boateng (scan, already on file) | 1 | 1 | 1 Power BI | 1 (MSc Data Science; BSc Psychology) | Yes | 4 | Phone screen |

Set the selector to REQ-031; create four candidates (name, email, phone, location, requisition), find Hannah's existing
record (REQ-029 application from April; a different "Lucia Romano" is also on file) and add a REQ-031 application to
it; fill five scorecards and five stage changes with reasons; save Grace's tracker from the mail, add five rows in Calc,
save as xlsx; reply to Grace with the tracker attached naming Priyanka Desai, Daniel Okafor and Hannah Boateng.
About 70-90 GUI steps.

**B**: read Ben's rules (no Monday - Ines away; no Tuesday morning - Ben at the dentist; earliest slot that works; the
first to reply gets a contested slot) and the replies in order: Chen (26 Oct, Tue/Wed any time) -> **Tue 3 Nov 14:00**
(Tue 10:00 blocked); Amara (27 Oct Wednesday, superseded on 29 Oct by Thu afternoon / Fri morning; Thu 15:00 is Dan's)
-> **Fri 6 Nov 10:00**; Leo (28 Oct, Mon pm / Tue pm / Thu am; Monday blocked, Tue 14:00 taken by Chen who replied
first) -> **Thu 5 Nov 09:30**; Sofia withdraws -> stage Withdrawn. Switch the selector to REQ-027, open each slot,
book, copy its video link; withdraw Sofia; save Ben's sheet from the mail, write the three names into the right rows,
save as xlsx; reply to Chen's, Leo's and Amara's *latest* mails with date, time and link. About 50-70 GUI steps.

## Shared live state and expected contention

- **One HireDesk session in one Chrome.** The requisition selector is a session setting: A works on REQ-031, B on
  REQ-027. When B switches to REQ-027 to see the interview slots, A's pipeline shows Product Designer candidates and -
  worse - A's next "New candidate" form opens with REQ-027 pre-selected, so a Data Analyst applicant silently lands on
  the wrong requisition (graded). When A switches back, B's Interviews page lists REQ-031 (no slots) or all
  requisitions. Pipeline filters/page are shared too. Logging out or re-logging in replaces the shared cookie.
- **One Thunderbird.** Both tasks' mails are interleaved in one Inbox (A needs 7, B needs 6), both open attachments
  (A: six CVs and a tracker; B: a panel sheet) and both compose replies with attachments/links. A Thunderbird restart
  kills the other's compose window.
- **One LibreOffice**: two Calc documents in one soffice process.
- No zero-sum element: A only touches REQ-031 candidates/applications, B only REQ-027 slots and one REQ-027 stage;
  each checker ignores the other's records (verified in both orders).

## Grading

`evaluate_screen` (A) - HireDesk db, the tracker, Drafts/Sent (attachments opened):

| weight | sub-check |
|---|---|
| 0.15 | each of the 5 applicants has a REQ-031 application (matched by email) |
| 0.225 | scorecard fields (4 scores + right to work) equal the ground truth (fraction of 25) |
| 0.15 | stage equals the decision (Lucia's rejection reason must mention right to work / visa / sponsorship) |
| 0.10 | no duplicate candidate record (Hannah) and no applicant / new candidate put on another requisition |
| 0.025 | all five decisions right |
| 0.175 | tracker rows (found by email or surname): SQL, Py/R, BI, degree, RTW, total, decision (fraction of 35) |
| 0.10 | reply to Grace has an xlsx attachment listing all five applicants (attachment content cross-check) |
| 0.05 | reply names the three shortlisted candidates |
| 0.025 | it is a reply to Grace's message |

Caps: no REQ-031 application at all -> <= 0.3; tracker missing/unreadable -> <= 0.6; k wrong decisions -> <= 0.85 - 0.1 k.

`evaluate_sched` (B):

| weight | sub-check |
|---|---|
| 0.30 | Chen, Leo, Amara booked in exactly their slots (fraction) |
| 0.10 | no wrong booking: Sofia not booked, Monday/Tuesday-morning slots free, nobody in a second slot, Dan's booking intact (and >= 1 right) |
| 0.10 | Sofia's application is Withdrawn |
| 0.15 | panel sheet: the three slot rows (by date + time) carry the right names; a stray name elsewhere costs 0.5 |
| 0.15 | a draft to each of the three candidates |
| 0.15 | each has the slot's date (3 Nov / Nov 3 / 03/11 / ISO), time (14:00 / 2pm ...) and HireDesk link code |
| 0.05 | each is a reply to the candidate's latest message (Amara's second mail) |

Caps: no correct booking -> <= 0.3; panel sheet missing -> <= 0.75.

## Self-test (offline, node 0, `lib_xtest_x2.py`)

Simulated Guest home; `app_x2.py` under python3.10 on a free port driven over HTTP (selector switches, new candidate,
add-to-requisition, scorecards, stages, slot bookings), 18 pages crawled under three selector states without errors;
Thunderbird emulated on the mbox files; setups run twice.

| run | screen | sched |
|---|---|---|
| pristine | 0.0 | 0.0 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference) | 1.0 | 1.0 |
| A sloppy (scored Daniel's first CV, missed Lucia's sponsorship line) / B ignored reply order (Leo got Tue 14:00, Chen Wed) and forgot Sofia | 0.65 | 0.375 |
| A under contention (Tom and Lucia created on REQ-027 because the selector had been switched; Lucia fixed by adding REQ-031) / B used Amara's superseded reply (Wednesday) | 0.75 | 0.658 |

## Provenance

CV screening against a hiring manager's scoring rubric with a right-to-work knockout and an ATS that must not get
duplicate candidate records, and scheduling panel interviews from candidates' free-text availability replies under
panel constraints, are the two core daily tasks of in-house recruiting coordinators (Greenhouse/Workable/Teamtailor
"scorecard" and "schedule interview" workflows; UK right-to-work rules mean "needs sponsorship" is a common knockout).

## Known risks

- Scanned CVs at 150 dpi are readable on screen when zoomed; an agent that only extracts PDF text sees nothing for
  Tom, Hannah and Daniel's updated CV (by design).
- Draft date/time detection uses regexes (3 Nov / November 3 / 03/11 / 2026-11-03; 14:00 / 2pm / 2:00 pm); unusual
  formats such as "the third" would miss.
- Panel-sheet rows are found by the date/time text Ben wrote ("Tue 3 Nov 2026", "14:00"); if the agent retypes those
  cells in another format the row is not found.
