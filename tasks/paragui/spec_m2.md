# m2: meeting requests → calendar vs. address-book clean-up (family F2, one Thunderbird)

## Scenario and persona
Dr. Amara Okafor is Director of Clinical Programs at Harbor Point Community Health, a Boston community health
centre (`amara.okafor@harborpointhealth.org`). Her chief of staff, Grace Liu, has gone on leave. Grace left two handover
e-mails:
- how she runs Amara's calendar;
- an address-book to-do list.

Amara gives one assistant each. Thunderbird 115 runs an offline POP3 profile with 18 Inbox messages. The profile has:
- an **enabled** local "Home" calendar (the base profile ships it disabled; we enable it), with calendar time zone
  America/New_York, the mail identity attached, and invitation e-mails switched off by default;
- a seeded Personal Address Book with 19 cards, including 3 people who appear twice and 1 leaver.

## User requests (verbatim)
**pgm2calendar (A)**
> My chief of staff Grace is on leave, so you are handling my calendar now. Several people emailed me meeting requests for the week of 16 November 2026 - please put all of them into my calendar in Thunderbird (the Home calendar), following Grace's handover email "How I handle your calendar (handover)" in my inbox: the right date, start and end time, the room or video link as the location, and everyone named in the request as attendees (use the email addresses given in the requests). If someone does not get their first-choice slot, reply to their request telling them the time you booked - save those replies as drafts, don't send them, and don't send any invitations.

**pgm2contacts (B)**
> Before going on leave, my chief of staff Grace left me a to-do list for my Thunderbird address book (her email "Address book clean-up"). Please do it in my Personal Address Book: merge the duplicate contacts into one card per person (the address they currently email me from is the primary email, their other address the secondary email), delete the card of the person who left, add the new people she lists with name, email, organization, job title and work phone taken from their email signatures or business card, and create the mailing list she describes. When the address book is clean, export it as a CSV file to ~/Documents/HPCH_contacts.csv.

## Content (hidden facts)
**Grace's rules:**
- Monday to Friday, 9:00–17:00 only.
- Wednesday mornings are blocked (clinic rounds).
- Overlaps are resolved by priority: Board > funders/government > internal staff. The lower-priority meeting takes the
  requester's alternative slot.
- A request without a stated length is 30 minutes.
- The location field holds the room or the video link.
- Everyone named in the request is an attendee.
- If someone does not get their first-choice slot, reply to them.
- The latest e-mail wins.

**Correct calendar** (local time):

| Event | When | Location | Attendees |
|---|---|---|---|
| Finance committee pre-read (Board) | Tue 17 Nov 10:00–11:00 | Boardroom 3B | Margaret Doyle, Robert Tan |
| Jamal 1:1 | **Thu 19 Nov 14:00–14:30** | his office | Jamal |
| Lindqvist Foundation debrief | **Wed 18 Nov 14:00–15:30** | Zoom link | Ingrid, Paul |
| Mobile clinic MOU review (BPHC) | **Fri 20 Nov 11:00–12:00** | City Hall Room 210 | Luis Ferreira, Nadia Haddad |
| Quarterly program review | Thu 19 Nov 9:30–11:00 | Harbor Room | 4 staff |
| Volunteer appreciation planning | **Mon 16 Nov 15:00–15:45** | Room 2.14 | Kayla |

Why the bold slots differ from the first choice:
- **Jamal 1:1:** he asked for Tue 10:30 with no length, so 30 minutes. That clashes with the Board meeting, so his
  alternative applies.
- **Lindqvist debrief:** first proposed 13:00–14:30; a later e-mail moves it by one hour.
- **MOU review:** first choice was Wednesday 10:00, which is blocked, so the alternative applies.
- **Volunteer planning:** the winning slot exists **only in the poll screenshot PNG**.

**Replies:** Jamal (new time Thursday 14:00) and Luis (Friday 11:00).

**Stale addresses:** the address book holds stale addresses for Ingrid and Luis (old foundation and health-department
domains). Auto-complete can pick them.

**Address book.** Merges, as (primary, secondary):

| Person | Primary | Secondary | Note |
|---|---|---|---|
| Jamal Whitaker | work address | gmail | |
| Ingrid Lindqvist | lindqvistfdn.org | old lindqvist-foundation.org | the richer old card holds the old address |
| Luis Ferreira | boston-health.gov | old bphc-boston.org | |

- Delete Tom Becker.
- Add four new contacts:

| Contact | Source |
|---|---|
| Margaret Doyle (board chair / partner) | signature |
| Paul Mercer (Grants Manager) | signature |
| Helen Park (Medical Director) | **only on a scanned business-card JPG**; she wrote from a personal gmail, but the card has her work address |
| Priya Shah (Data Analyst) | signature |

- Create the list "Program Leads": Nadia, Jamal, Rosa, Kayla, Priya.

## Shared resources and expected contention
- **One main window, two tabs.** A works in the Calendar tab plus the event dialog and the attendee dialog. B works in
  the Address Book tab plus card editing. Both keep returning to the Mail tab to read the same e-mails. Switching tabs
  changes what the other agent sees, and every new screenshot can show the other agent's tab.
- **Shared data.**
  - A's attendee fields auto-complete from the address book B is merging and deleting. A can pick a stale duplicate,
    or a card that disappears mid-edit.
  - The new contacts B must add (Margaret, Paul) appear in the meeting requests A is processing.
  - The address-book export B writes reflects whatever state the cards are in at that moment.
- **Dialogs.** The event dialog and the attendee picker are separate windows. Focus theft between them and B's card
  editor is likely.
- **Independent graders.** A is graded on calendar plus drafts. B is graded on `abook.sqlite` plus the CSV. Neither
  task's legitimate work changes the other's graded state, so both orders work.

## GUI-only parts
- **A:**
  - Calendar events, with attendees, are Thunderbird-internal (`calendar-data/local.sqlite`, held open by
    Thunderbird).
  - The poll result exists only as pixels.
- **B:**
  - The address book is Thunderbird-internal (`abook.sqlite`, cached by the running app).
  - Thunderbird 115 has no merge feature: merging is manual card editing.
  - Helen Park's details exist only on the card image.

## Grading
**pgm2calendar** (`evaluate_calendar`). The checker reads `local.sqlite` through a Guest copy that includes the -wal
file. Times are compared as Boston wall-clock times; floating times are taken as they are.

| Check | Weight |
|---|---|
| Per expected event (matched by title keywords): exact start and end | 0.06 each |
| Per expected event: location token (Zoom ID for the debrief) | 0.02 each |
| Per expected event: attendees ⊇ required and ⊆ allowed (a stale address fails) | 0.03 each |
| No duplicates or extra events that week (e.g. the first-choice slot left in place), needs ≥ 3 correct times | 0.08 |
| Grace's rules hold for the whole week (no overlap, nothing Wednesday morning, 9–17), needs ≥ 4 correct times | 0.08 |
| Reply drafts to Jamal and Luis exist (In-Reply-To + To) | 0.03 each |
| Each reply's own text (quote stripped) states the booked day and time | 0.06 each |

The six events give 0.66, the two global checks 0.16 and the replies 0.18.

**pgm2contacts** (`evaluate_contacts`). The checker reads the `abook.sqlite` dump, preferring `_vCard`, then the
derived `PrimaryEmail`/`SecondEmail` rows.

| Check | Weight |
|---|---|
| Per merge: exactly one card holds both addresses and the primary is correct | 0.06 each |
| Per merge: that card carries the right name | 0.02 each |
| Leaver deleted | 0.05 |
| The other 12 original contacts still exist (only once some progress is made) | 0.05 |
| Per new contact: primary email | 0.03 each |
| Per new contact: name | 0.01 each |
| Per new contact: organization | 0.01 each |
| Per new contact: title (alternatives allowed, e.g. "Chair"/"Partner" for Margaret) | 0.01 each |
| Per new contact: phone | 0.02 each |
| List "Program Leads" exists | 0.04 |
| List members: (correct − extra)/5 | 0.12 |
| CSV exists | 0.04 |
| CSV contains every final primary address, each merged person on one row with both addresses, and no leaver | 0.08 |
| CSV has one e-mail row per card currently in the book (catches an export made before the clean-up) | 0.06 |

## Reference solution and expected effort
**A:**
- read 8 relevant mails and the poll (about 12 steps)
- create 6 events with time, location and attendees (about 12 each, so 70)
- 2 reply drafts (about 14)

About **95 GUI steps**; 30–40 minutes for a person.

**B:**
- find the duplicates (about 6 steps)
- 3 merges (about 8 each)
- 1 delete (3)
- 4 new cards (about 10 each)
- the list (about 10)
- the export (about 6)

About **90 steps**; 30–40 minutes.

## Provenance
- **A** is the classic executive-assistant workflow: turn e-mailed meeting requests into calendar events under
  scheduling rules, resolve a clash by priority, handle a rescheduling mail and a poll screenshot.
- **B** is the common "clean up my contacts" request: duplicates from old addresses, leavers, new contacts from
  signatures and a business card, and a distribution list. "How to merge contacts in Thunderbird" is a long-standing
  support-forum question.

## Self-test (offline, simulated Guest; `lib_m2test.py`)
| Case | Score |
|---|---|
| Pristine: calendar / contacts | 0.000 / 0.000 |
| A then B: calendar / contacts | 1.000 / 1.000 |
| B then A: contacts / calendar | 1.000 / 1.000 |
| Partial A: first-choice slots, stale Ingrid address, no replies | 0.530 |
| Partial A: skipped the poll screenshot and the Zoom debrief | 0.780 |
| Partial A: replies that do not state the new time (only the quoted request does) | 0.880 |
| Partial B: old addresses kept as primary, CSV exported before the clean-up | 0.700 |
| Partial B: no merges, half the list, no export | 0.508 |

## Known risks
- I checked the storage formats against comm-esr115 source: `cal_events` stores PRTime in µs plus a tz id; ORGANIZER
  and ATTENDEE lines go in `cal_attendees`; LOCATION is in `cal_properties`; `abook.sqlite` has `_vCard` plus derived
  rows. I could not run Thunderbird itself.
  - The seeded cards follow the 115 format (`_vCard` plus derived rows). The loader also accepts legacy rows.
- `calendar.itip.notify=false` makes "Notify attendees" unchecked by default (verified in `calendar-item-iframe.js`).
  If an agent ticks it, Thunderbird would try SMTP and show an error. The event is still saved.
- The CSV export column layout was not verified. The checker only uses the e-mail addresses per row, so the layout
  does not matter.
