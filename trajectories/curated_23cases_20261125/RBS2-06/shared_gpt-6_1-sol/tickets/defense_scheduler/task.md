# Thesis Defense Calendar (.ics) & Room Tariff Scheduling Work Order — `defense_scheduler`

## Scope & Deliverables
Schedule all 12 thesis defenses (`DEF-01` .. `DEF-12`) on `2026-12-04` using **MailDesk Client** on the desktop and `/workspace/maildesk/maildesk.sqlite`, and update the room-cost section of `/workspace/contracts/Contract_Schedule.xlsx` (currently open in LibreOffice Calc with an active desk tag in `Vendor_SLAs!C1`).

Deliverables:
1. **Conflict-Free Schedule in SQLite (`/workspace/maildesk/maildesk.sqlite`)**:
   - Assign each `DEF-01..DEF-12` in `defense_threads` (`assigned_room`, `assigned_slot`, `status='SCHEDULED'`) across rooms `HALL_A` (cap 45, `$450/slot`), `HALL_B` (cap 28, `$280/slot`), and `SEM_C` (cap 16, `$150/slot`) and slots `09:00, 11:00, 13:00, 15:00, 17:00` so that: (a) room capacity `>= expected_attendees`, (b) `assigned_slot` is in `candidate_avail_slots_csv`, (c) none of the 3 red maintenance blackout cells shown on MailDesk's Room Matrix canvas is booked, (d) no `(room, slot)` is double-booked, and (e) no `chair_prof` chairs two defenses in the same time slot.
2. **RFC-5545 Calendar Export (`/workspace/schedule/defense_calendar.ics`)**:
   - Valid `VCALENDAR` containing 12 `VEVENT` blocks (`UID:DEF-01` .. `UID:DEF-12`, `SUMMARY` including `candidate_name`, `LOCATION` set to `HALL_A`/`HALL_B`/`SEM_C`, and `DTSTART`/`DTEND` on `20261204T090000..20261204T184500`).
3. **Spreadsheet Room Envelope (`/workspace/contracts/Contract_Schedule.xlsx`)**:
   - Update `Budget_Envelope!B2:B4` with booked slot counts for `HALL_A`, `HALL_B`, and `SEM_C`, preserve formula `=B2*450+B3*280+B4*150` in `B5`, and record `calendar_organizer_seal` (from MailDesk `Preferences` / `Ctrl+B`) in `Budget_Envelope!B6`, preserving all other rows/sheets and `Vendor_SLAs!C1` (`CONTRACT-DESK-906`) with the open Calc window kept in sync.
