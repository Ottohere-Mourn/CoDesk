# m3: trip itinerary + calendar vs. inbox reorganisation (family F2, one Thunderbird)

## Scenario and persona
Lukas Brandt is a senior consultant at Aldervane Consulting in Munich (`lukas.brandt@aldervane.de`). In December he
travels:
- to Vienna for a two-session client workshop at Donauwerke AG;
- then to Copenhagen for the NordData Summit.

Lukas hands two chores to two assistants:
- one prepares the trip;
- the other finally cleans up his overflowing inbox.

Thunderbird 115 runs an offline POP3 profile with 33 Inbox messages, dated Dec 2025 to Oct 2026. The calendar time
zone is Europe/Berlin.

## User requests (verbatim)
**pgm3trip (A)**
> In December I travel to Vienna (client workshop at Donauwerke) and on to Copenhagen (NordData Summit); all the booking confirmations are in my Thunderbird mailbox (lukas.brandt@aldervane.de). Please: 1) save the train e-ticket, the Austrian Airlines itinerary and the Copenhagen hotel confirmation PDFs into ~/Documents/Travel/; 2) write an itinerary document ~/Documents/Travel/Itinerary_Dec2026.docx that lists everything in chronological order - each journey with date, departure and arrival time and booking reference, each hotel with check-in and check-out dates and confirmation number, the two workshop sessions and the conference days; 3) add the train ride and both flights to my Thunderbird calendar, each from departure to arrival time with the booking reference in the event, plus the NordData Summit as an all-day event covering its two days; 4) reply to the travel desk's pre-approval request with the total cost of transport and hotels, and save the reply as a draft. If a booking was changed later, use the latest information; use the local times printed on the bookings.

**pgm3inbox (B)**
> My Thunderbird inbox (lukas.brandt@aldervane.de) needs a clean-up. Under my account, create a folder Travel and a folder Projects with the subfolders Donauwerke, Helios and Marlow. Move every mail about one of these three client projects into its project folder (the clients write from donauwerke.at, helios-energie.de and marlowretail.co.uk; colleagues put the project name in the subject) and every booking confirmation or other travel-related mail into Travel. Archive everything else I received before 1 October 2026 with Thunderbird's Archive function. Star every message in which someone asks me to do something by a specific date, wherever it ends up, and create a saved search folder called "Follow-up" under my account that shows all starred messages from all of these folders. Finally, write ~/Documents/followups.txt with one line per starred message: the deadline as YYYY-MM-DD, the sender's name and the subject.

## Content (hidden facts)
**Trip.** All bookings are in the same time zone (CET), so local times are unambiguous.

| Item | Source | Reference | When | Cost |
|---|---|---|---|---|
| Train RJX 63 München–Wien | **image-only e-ticket PDF** | 7KQ4MZ | 9 Dec 08:24–12:30 | €89.90 |
| Hotel Lindengarten | HTML mail body | LGW-48213 | 9–10 Dec | €164.00 |
| Flight OS 305 VIE–CPH | text PDF itinerary | QX4T7B | 10 Dec 17:05–18:55, **changed by a later mail to 17:35–19:25** | €212.40 |
| Nyhavn Harbour Hotel | **image-only PDF** | NHH-20931 | 10–12 Dec | €398.00 |
| SK 1637 CPH–MUC | mail body | 8ZPLMK | 12 Dec 19:40–21:35 | €176.30 |
| Workshop sessions | client mail | | 9 Dec 14:00–17:30 and 10 Dec 09:00–13:00 | |
| NordData Summit | registration mail | | 11–12 Dec | fee €650, paid by Marketing, excluded |

The travel-desk total is **€1,040.60**.

**Inbox.** 33 messages:

| Destination | Count |
|---|---|
| Travel | 8 |
| Projects/Donauwerke | 5 |
| Projects/Helios | 4 |
| Projects/Marlow | 3 |
| Archives | 7 (before 1 Oct and not project or travel; includes one from 2025) |
| Stay in the Inbox | 6 |

- Three project mails are older than 1 October. They must go to their project folder, not the archive.
- Five mails ask for something by a date. These must be starred:

| Mail | Deadline |
|---|---|
| Travel desk | 2026-11-20 |
| Donauwerke agenda | 2026-11-27 |
| Helios tariff comments | 2026-11-06 |
| Marlow CR-14 | 2026-10-30 |
| HR vacation plan | 2026-11-15 |

- Distractors that must not be starred:
  - a request with no date (new VPN client);
  - an event date with no request (all-hands);
  - a marketing "offer ends 31 October";
  - a lunch invitation.

## Shared resources and expected contention
- **B moves A's source mails.** B moves exactly the mails A is working from: all 8 travel mails go to Travel, and the
  client mail with the workshop times goes to Projects/Donauwerke. This happens while A is reading them, saving their
  PDFs or replying to the travel desk. B also archives and stars.
- **Shared window and focus.**
  - A switches to the Calendar tab and opens event dialogs; B's message list disappears from view.
  - B's archive and move operations change the selection under A's open message.
  - Both open dialogs: Save Attachment, New Folder, Saved Search. They steal focus from each other.
- **Order independence.**
  - A's checker does not depend on where the mails are.
  - B's checker ignores Drafts. A's reply to the travel desk does not touch its star or its folder.
  - Both orders are legitimate.

## GUI-only parts
- **A:**
  - The train ticket and the Copenhagen hotel confirmation are pixels only.
  - Calendar events are Thunderbird-internal.
  - The schedule change exists only as a later mail.
- **B:**
  - Moving, archiving and starring inside a running Thunderbird. Editing mbox files behind its back corrupts its view.
  - The saved search is stored in `virtualFolders.dat`, written by the app.
  - Deciding which mails carry a deadline requires reading them.

## Grading
**pgm3trip** (`evaluate_trip`)

| Check | Weight |
|---|---|
| 3 PDFs in `~/Documents/Travel/` (md5) | 0.12 |
| Itinerary document exists (.docx; .odt accepted) | 0.04 |
| 5 booking references | 0.10 |
| 6 current journey times | 0.08 |
| No stale "17:05" (with ≥ 4 times correct) | 0.04 |
| Workshop sessions (Donauwerke, 17:30, 13:00) | 0.04 |
| Conference mentioned | 0.02 |
| Chronological order of the refs (transport and hotels) | 0.04 |
| Calendar, per journey: exact local start and end | 0.06 each |
| Calendar, per journey: booking reference in title, description or location | 0.03 each |
| NordData all-day event(s) covering exactly 11 and 12 Dec | 0.07 |
| Reply draft to the travel desk | 0.06 |
| Its own text states 1,040.60 | 0.12 |

**Cap:** no itinerary document → ≤ 0.5.

**pgm3inbox** (`evaluate_inbox`)

| Check | Weight |
|---|---|
| 5 folders exist | 0.05 |
| Each of the 27 mails that must move is only in its target (archives: any `Archives/<year>`) | 0.40 |
| The 6 stay-in-Inbox mails are untouched (only counted once something moved) | 0.06 |
| Stars: (correct − extra beyond 1)/5 | 0.20 |
| Saved search "Follow-up" exists | 0.03 |
| Its terms contain `(status,is,flagged)` | 0.05 |
| Its scope covers every folder holding a starred mail (or the account root) | 0.06 |
| `followups.txt`: per starred mail, one line with the date and its sender or subject; extra dated lines are subtracted | 0.15 |

## Reference solution and expected effort
**A:**
- read about 9 mails and 3 PDFs (about 15 steps)
- save 3 PDFs (about 9)
- write the itinerary in LibreOffice Writer (about 25)
- 4 calendar events (about 32)
- reply draft (about 8)

About **90 GUI steps**; 30–40 minutes.

**B:**
- 5 folders (about 15 steps)
- about 27 moves or archives using multi-select (about 35)
- 5 stars (about 10)
- the saved search (about 10)
- the text file (about 8)

About **80 steps**; 25–35 minutes.

## Provenance
- **A** is the standard travel-planning chore from consulting and business-travel workflows: consolidate the
  confirmations, honour a schedule change, put the trip into the calendar, and answer the travel desk's pre-approval.
- **B** is "inbox zero by project plus archive plus follow-ups" (GTD style), including Thunderbird's Archive feature
  and saved searches as a follow-up view. Both are commonly documented Thunderbird workflows.

## Self-test (offline, simulated Guest; `lib_m3test.py`)
| Case | Score |
|---|---|
| Pristine: trip / inbox | 0.000 / 0.000 |
| A then B: trip / inbox | 1.000 / 1.000 |
| B then A: inbox / trip | 1.000 / 1.000 |
| Partial A: missed the schedule change and the Vienna hotel cost | 0.753 |
| Partial A: no itinerary document | 0.500 |
| Partial B: no archive, 3 extra stars, saved search on the Inbox only | 0.756 |
| Partial B: folders and archive only | 0.510 |

## Known risks
- Archive granularity is the Thunderbird default (yearly, by message date), so the archive folders are
  `Archives/2025` and `Archives/2026`. The checker accepts any folder under `Archives`.
- If an agent archives *project* mail older than 1 October instead of filing it, that counts as wrong, as the
  instruction intends.
- The `virtualFolders.dat` format was verified against comm-esr115 (`nsMsgAccountManager::SaveVirtualFolders`). The
  exact scope Thunderbird stores when the dialog's "search subfolders" option is used was not verified. The checker
  accepts either the explicit folder list or the account root.
