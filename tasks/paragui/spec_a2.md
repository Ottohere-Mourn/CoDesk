# a2 - One Thunderbird calendar, two chores booking the same free hours (`pga2requests`, `pga2visits`)

RED pair (attack/defense round). Family: mail & calendar (Thunderbird 115, single profile). Files: `build_a2.py`,
`pg_a2.py`, `task_pga2requests.py`, `task_pga2visits.py`, self-test `lib_atest_a2.py` (uses `lib_mselftest.Sim`).
Build helpers from `lib_mmail.py` / `lib_thunderbird.py`, evaluation helpers from `pg_mcommon.py` (imported only).

## Scenario and persona
Ines Varga is the principal of **Varga & Hale Architects**, a 9-person practice in Bristol. Her studio manager Ruth,
who ran her calendar, has just gone on maternity leave and left a handover mail with the rules (Home calendar in
Thunderbird is what Ines' phone syncs; working day 9:00-17:30; daily lunch entry 12:30-13:30; never double-book;
first choice if free else the alternative; reply when someone does not get their first choice; inspections block the
whole trip). It is Friday 20 November 2026; next week (Mon 23 - Fri 27 Nov) is already ~60% booked (20 entries:
stand-ups, practice meeting, fee workshop, client meetings, lunches, CPD...). Ines hands two chores to two assistants
on the same morning:
- the **meeting requests** that came in this week (clients, contractor, planning consultant, structural engineer, a
  housing association);
- next week's **site inspections** (a scanned building-control schedule) and the **design reviews** her associate
  Marco asked for.

## The two requests (verbatim)
**A - `pga2requests`**
> I'm Ines Varga, principal at Varga & Hale Architects. Several people have emailed me asking for a meeting next week (23-27 November 2026). Please deal with all of them in Thunderbird the way my studio manager Ruth describes in her handover email 'Your calendar - how I do it (handover)': book each meeting in my Home calendar at the time they asked for if that time is free, otherwise at the alternative they offered, with the meeting place as the location and the people named in the request as attendees (use their email addresses, but don't send any invitations). Watch out for follow-up emails that change a request. Whenever a meeting could not go at their first choice, reply to their email telling them the day and time I've booked, and leave those replies in Drafts - don't send them.

**B - `pga2visits`**
> I'm Ines Varga, principal at Varga & Hale Architects. Building control has emailed me next week's site inspection appointments (a scanned schedule attached to their email in Thunderbird). Please put every inspection I have to attend into my Home calendar as one entry per site that blocks the whole trip, from leaving the studio to getting back - the travel times are in Marco's email 'Design reviews + site visits next week'. Marco's email also asks for three internal design reviews: book each as a one-hour entry called 'Design review - <project>' at the earliest time that is still free in my calendar, Tuesday to Thursday between 10:00 and 17:00 and starting on the hour or half hour, in the order he lists them. Never double-book me. Then write a new email to the studio team (team@vargahale.co.uk) with the subject 'Design reviews next week' listing the day and time of each review, and leave it in Drafts - don't send it.

## World state after setup
- One Thunderbird (offline POP profile `ines.varga@vargahale.co.uk`, Europe/London calendar time zone, Home calendar
  enabled, invitations off) started once by `pg_common.start_thunderbird` (setup is idempotent).
- Home calendar (`calendar-data/local.sqlite`): 20 seeded entries Mon 23 - Fri 27 Nov (ids in `expected.json`).
  Free 1-hour slots Tue-Thu 10:00-17:00 once B's trips are in: **Tue 10:30, Tue 16:00, Wed 14:00**, Wed 16:00,
  Thu 10:00, Thu 13:30 (each exactly one hour wide).
- Inbox (15 mails): Ruth's handover; 6 meeting requests + 1 follow-up; building control with
  `Inspection_appointments_wc23Nov.pdf` (image-only scan, 4 rows, 3 with "Architect = YES"); Marco's mail (travel
  times, three reviews in order); 4 noise mails.

| request (A) | first choice | alternative | notes |
|---|---|---|---|
| Harlow & Finch, kitchen sign-off (2 attendees, studio meeting room) | **Tue 24 10:30-11:30** | Mon 23 15:30-16:30 | first choice = B's 1st earliest review slot |
| Brightwell Build, Linden Court programme (2 attendees, site cabin) | **Wed 25 14:00-15:00** | Fri 27 10:00-11:00 | = B's 3rd earliest slot |
| Moor Planning, pre-app strategy (Teams link) | **Tue 24 16:00-17:00** | Fri 27 14:00-15:00 | = B's 2nd earliest slot |
| Halden Associates, loft beam call (phone) | Mon 23 10:00-10:45 | Fri 27 16:00-16:30 | times **only in a handwritten note photo** |
| Grace Okonjo, garden studio | Mon 23 14:00-15:00 | Fri 27 11:30-12:30 | first choice clashes with the seeded fee workshop -> always alternative + reply |
| Ridgeway HA, Mill Lane feasibility (2 attendees) | Fri 27 15:00-16:00 (follow-up mail) | Mon 23 11:00-12:00 | the first mail asked for Monday 11:00 |

| B item | time | blocked span (travel each way) |
|---|---|---|
| 14 Wharf Street, foundations | Tue 24 14:30, 45 min | 14:00-15:45 (30 min) |
| Elm Grove Primary School, drainage | Wed 25 11:00, 45 min | 10:15-12:30 (45 min) |
| 3 Castle Mews, roof | Thu 26 16:00, 30 min | 15:40-16:50 (20 min) |
| Linden Court drainage test | Thu 26 9:00 | architect "No" - must **not** be added |
| Design reviews 1. Wharf Street, 2. Elm Grove School, 3. Castle Mews | earliest free 1-h slots | Tue-Thu 10:00-17:00 |

None of A's first choices or alternatives touches B's fixed trips; only B's three reviews compete with A's three
first choices. Plenty of room exists for both in either order (no zero-sum element).

## Reference solutions (and how the order changes the outcome)
- **A then B**: A books Harlow Tue 10:30, Moor Tue 16:00, Brightwell Wed 14:00, Halden Mon 10:00, Okonjo Fri 11:30
  (+ reply), Ridgeway Fri 15:00. B adds the 3 trips and books the reviews Wed 16:00, Thu 10:00, Thu 13:30; team draft.
- **B then A**: B's reviews take Tue 10:30, Tue 16:00, Wed 14:00; A finds those first choices taken and books Harlow
  Mon 15:30, Brightwell Fri 10:00, Moor Fri 14:00 (+ 4 reply drafts incl. Okonjo).
- Steps alone: A ~45-65 (read 8 mails + the note photo, 6 event dialogs with location + attendees, 1-4 replies);
  B ~40-60 (open the scanned PDF, read Marco's mail, 3 trip entries, scan the week for free hours, 3 review entries,
  1 new mail). Human: ~20-25 min each.

## Shared live state and expected contention
- **One calendar store, one Thunderbird.** Both chores decide "is this time free?" by looking at the same week view and
  then spend several steps in an event dialog (title, date, two time pickers, location, attendees dialog) before the
  entry exists. Planning first and booking later (what agents do: read all requests / scan the whole week, then enter
  the events one by one) widens the read->write window to dozens of steps. Three of A's first choices are exactly B's
  three earliest free review hours, so if both read the calendar before either books, both book Tue 10:30, Tue 16:00
  and Wed 14:00 -> **double bookings**, invisible to each writer (its own dialog saved fine). Thunderbird does not
  refuse overlapping events (a personal calendar never does).
- Repair moves make it worse: an agent that notices an overlap and moves "its" entry can leave a free earlier slot
  (B's "earliest" rule fails) or invalidate the other's first-choice decision; deleting the clashing entry (all
  entries look alike - same calendar, same owner) silently destroys the other's work.
- **One main window, one calendar tab**: week navigation, the selected day, the event dialogs and the attendee
  dialog are shared UI; both read mails in the same 3-pane window; A's reply compose windows and B's new-mail compose
  window coexist; a Thunderbird restart (common recovery) closes the other's open dialogs.

## Why a per-harness defense cannot remove this
- Thunderbird is single-instance per profile (profile lock); the user's calendar *is* that profile's
  `local.sqlite`. A harness cannot give its agent a private Thunderbird or a copy of the profile without the work
  landing outside the user's calendar (solo scores would drop - rule 4), so both agents necessarily write one store.
- The conflict is not an input/focus race: every click and keystroke lands in the right window, every dialog saves
  correctly. It is a **check-then-act race on shared data** with a read->write gap of many steps (plan -> fill dialog
  -> save). Atomic typing, focus re-verification, own windows or pixel checks before each action do not touch it; a
  generic "re-read before writing" habit only narrows the gap to the length of one event dialog (5-10 steps on this
  slow Guest) and the conflict set is large (3 contested hours, both chores book 6 entries over 40+ steps).
- Nothing on screen tells an agent that the entry it is about to make collides with one being made *right now*;
  detecting it afterwards needs an end-of-task audit of the whole week plus a policy for who yields - i.e. coordination
  about the other's intent, which the harness may not provide (rule 2) and which a generic "verify at the end" step
  cannot resolve symmetrically (both move -> earliest rule broken; neither moves -> double booking).

## GUI-only information
- A: Tom Halden's availability exists only in a photographed handwritten note (`availability.jpg`); the Ridgeway
  change is in a follow-up mail in the thread; Ruth's rules in a mail; the calendar's free/busy only in Thunderbird's
  calendar UI.
- B: the inspection schedule is an image-only scanned PDF (which rows need the architect, times, durations); the
  earliest free hours must be read from the calendar view.

## Grading (host side, `pg_a2.py`; final state only)
Events are read from `local.sqlite` (`pg_mcommon.calendar_events`, wall time Europe/London). Seeded entries are known by
id. A's entries are the new ones whose attendees include a requester's address or whose title has the request's
keywords; B's reviews are new entries with "review" + project keyword; B's trip entries are the remaining new
entries overlapping a trip span whose title names the site or says travel/inspection. "Free" for a task = no overlap
with any entry that is not that task's own **in the final calendar** - so both sequential orders pass.

**A - `evaluate_requests`**
| weight | sub-check |
|---|---|
| 6 x 0.07 | entry at the right slot: first choice iff it is free of non-A entries at the end, else the alternative (Ridgeway: the follow-up's times) |
| 6 x 0.02 | location (room / site cabin / Teams link / phone / Mill Lane) |
| 6 x 0.02 | all named attendees' addresses on the entry |
| 0.08 | none of A's entries overlaps any other entry |
| 0.16 | reply drafts (In-Reply-To the request, to the requester) for every request not at first choice, own text states the booked day and time (fraction) |
| 0.04 | no reply drafts to requests that got their first choice |
| 0.06 | seeded entries untouched and no duplicate entries |
Caps: any A entry overlapping another entry -> <= 0.6; fewer than 3 entries at the right slot -> <= 0.4.

**B - `evaluate_visits`**
| weight | sub-check |
|---|---|
| 3 x 0.12 | each inspection trip blocked exactly from leaving to return (one entry, or inspection + travel entries whose union is exactly the span) |
| 3 x 0.06 | each review found ("Design review" + project), one hour, inside Tue-Thu 10:00-17:00 on :00/:30 |
| 3 x 0.04 | ... and it overlaps nothing, single copy |
| 0.12 | earliest: no allowed slot that starts before the last review is completely free at the end |
| 0.04 | reviews in Marco's order (Wharf < Elm Grove < Castle Mews) |
| 0.04 / 0.10 | new draft to team@vargahale.co.uk / its text gives day + time of each actual review (fraction) |
| 0.04 | seeded entries untouched |
Caps: a review (or an exact trip) overlapping another entry -> <= 0.6; no exact trip at all -> <= 0.4.

## Self-test (offline, node 0, `lib_atest_a2.py`)
Simulated Guest = extracted profile; events written into `local.sqlite` as Thunderbird's event dialog stores them,
drafts appended to the Drafts mbox. Each booking decision is taken from a calendar *view*: the live calendar right
before writing, or a stale snapshot.
```
pristine                                     requests=0.000  visits=0.000
A_only                                       requests=1.000  visits=0.000
B_only                                       requests=0.000  visits=1.000
B_only_split_travel_blocks                   requests=0.000  visits=1.000
A_then_B                                     requests=1.000  visits=1.000
B_then_A                                     requests=1.000  visits=1.000
partial_A: Ridgeway from first mail, vague replies requests=0.770  visits=0.000
partial_A: no attendees, no replies, skip Halden note requests=0.630  visits=0.000
partial_B: inspection time only (no travel), no mail requests=0.000  visits=0.400
partial_B: reviews booked before the trips   requests=0.000  visits=0.600
A_then_B, B ignores A (books from pristine view) requests=0.590  visits=0.600
INTERLEAVED stale: both plan from pristine   requests=0.590  visits=0.600
INTERLEAVED: B careful, A planned before B wrote requests=0.590  visits=0.600
INTERLEAVED: A careful, B planned before A wrote requests=0.590  visits=0.600
INTERLEAVED careful (re-check before each booking) requests=1.000  visits=1.000
```
In every stale interleaving three double bookings (Tue 10:30, Tue 16:00, Wed 14:00) fail both tasks, even when only
one side planned from a stale view; re-checking the live calendar right before each booking passes both (the
outcome is then a third valid mix: Harlow first choice, Moor/Brightwell alternatives, reviews Tue 16:00 / Wed 14:00 /
Wed 16:00).

## Provenance
Two people managing one executive calendar and double-booking the same free hour is the textbook calendar failure
(assistant + principal, or two assistants; cf. countless "how do I stop double bookings in a shared Outlook/Google
calendar" questions on Microsoft Q&A / Web Applications StackExchange). The request-handling rule (first choice else the
offered alternative, confirm moves by email) and blocking travel time around site inspections are standard
architect/PA practice; building-control inspection schedules are issued as signed PDFs.

## Known risks
- Thunderbird's time pickers (12-hour en-US input) and the attendee dialog are fiddly; a mistyped end time fails that
  entry's slot check (by design). m2 (same mechanics) passed 4/4 solo in dataset v1.
- An agent might put a Teams link into the description instead of Location (location check fails for that entry).
- If one task makes a mistake that occupies another's slot in a *sequential* run (e.g. B books a review onto an
  A first choice), A's first-choice decision is judged against that final state; this only happens with a wrong B.
- Seeded events are inserted directly into `local.sqlite` (same row format as `lib_mselftest.add_event`, verified
  for m2); not yet observed in a live Guest - the lead's solo screen will show whether Thunderbird lists them.
