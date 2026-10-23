# X3 - A practice's anniversary client evening: RSVPs vs catering (`pgx3rsvp`, `pgx3catering`)

Family F6 (cross-application workflows). Files: `build_x3.py`, `app_x3.py`, `pg_x3.py`, `task_pgx3rsvp.py`,
`task_pgx3catering.py`, shared helpers `lib_x.py` (build), `pg_xcommon.py` (evaluation), `lib_xtest.py` +
`lib_xtest_x3.py` (offline self-test).

## Scenario and persona

Rosa Lindqvist is office manager of **Brightwater Studio**, a 20-person architecture practice in Bristol. The
practice turns 15 and holds a client and partner evening on Thu 19 Nov 2026 at The Glasshouse (drinks, canapés,
seated dinner). Rosa sent the invitation by email (it is in her Sent folder) asking each invitee to reply with
attendance, a plus-one name, a main course for each person and dietary needs. The replies have piled up; the venue
wants final numbers and a door list, and the caterer is waiting for the order. The office runs **Brightwater Hub**, a
small intranet with an Events module (guest lists, hosts, CSV door-list export) and a Purchasing module (approved
suppliers, catalogues, purchase orders charged to an event). Director Martin Achebe has written the rules in one mail
and started a draft catering order (PO-2026-0144) with rough numbers.

Rosa gives the RSVP admin to one assistant and the catering to the other. One Thunderbird
(rosa@brightwater-studio.co.uk, offline POP profile), one Chrome with Hub open (both log in as `rosa`), LibreOffice.

## The two requests (verbatim task instructions)

**A - `pgx3rsvp`**
> I'm organising Brightwater Studio's 15th-anniversary client evening on 19 November. The replies to my invitation are
> in my Thunderbird inbox, and Martin's email 'Anniversary evening - arrangements' has the rules. Please record every
> reply in the anniversary guest list on our Hub (http://127.0.0.1:8123, username rosa, password Glasshouse15): who is
> coming or not, the name of their plus-one, and anyone coming in someone else's place - a later email from the same
> person overrides an earlier one. Move every RSVP email you have dealt with into a new folder 'Anniversary RSVPs' under
> my account. Then save the door list (every expected guest including plus-ones, with their company - not our own
> staff) as ~/Documents/Events/Anniversary_door_list.xlsx, and write an email to Clara at The Glasshouse with the final
> total headcount and the door list attached, copying Martin, and tell Martin in it about anyone who asked to come on a
> forwarded invitation. Leave the email in Drafts - don't send it.

**B - `pgx3catering`**
> Please sort out the catering for our anniversary client evening on 19 November. Use the replies to my invitation in
> Thunderbird (each guest and plus-one chose a main course and told us about dietary needs; a later email from the same
> person overrides an earlier one) and our hosts' choices on the event page in our Hub (http://127.0.0.1:8123, username
> rosa, password Glasshouse15). Martin started the Fennel & Fig order in Hub Purchasing, and his email 'Anniversary
> evening - arrangements' says what everyone gets: finish that order with the right quantities, charged to the
> anniversary evening, and submit it. Then put the order's total and PO number into the catering line of
> ~/Documents/Events/Anniversary_Budget_2026.xlsx and update the total and the remaining budget there. Finally write an
> email to Dev at Fennel & Fig with the PO number and the guests who have allergies or dietary requirements, by name.
> Leave it in Drafts - don't send it.

## World state after setup

- **Brightwater Hub** (`app_x3.py`, port 8123, db `~/.local/share/intranet/hub/app.db`): events "Anniversary Evening
  2026" (36 invitees, all *Invited*; 6 staff hosts with their main course / dietary / drinks shown only on the event
  page) and "Winter Party 2026" (12 staff guests). The header **Event selector** is stored in the login session and
  defaults to *Winter Party 2026* at login; it scopes the guest list, the CSV export, the home page, the "This event"
  purchase-order list and the default "charge to" of a new PO and of "Add guest". Guest-list filters (status, search,
  page of 12) are stored in the session too. The guest list edits status + plus-one inline (one Save per row); the
  detail page also has main course / dietary / notes. Purchasing: 5 suppliers; Fennel & Fig catalogue of 13 items
  (canapés, four mains, children's main, two desserts, drinks / soft-drinks packages, premium wine, late bites,
  waiting staff), 12.5% service + 20% VAT computed per PO; POs 0141 (venue) and 0142 (AV) submitted, 0143 Fennel & Fig
  for the Winter Party (submitted, a tempting template), 0144 Martin's Anniversary draft (30 canapés, 10/10/10 mains,
  30 desserts, 30 drinks, 30 late bites). Draft lines can be updated/removed/added; submitted POs are read-only
  (cancel is possible). Activity log of every change.
- **Thunderbird** Inbox (22 mails): 16 RSVP mails (13 invitees, Ben Carter twice - yes, then cancels; Olivia Grant
  twice - plus-one's choice and coeliac note in the second; Daniel Fischer sends his colleague Laura Mensah instead;
  Anna "same for both of us"; Grace vegan + no alcohol; Raj "Anita is vegan"; Hugo shellfish allergy; Helen Park's PA
  sends a **phone photo of the paper reply card** (guest David Park, initials next to the chosen mains, "David - nut
  allergy (severe!)"); Marcus Webb asks to come on a **forwarded** invitation), Martin's rules, Clara (venue) asking for
  numbers + door list, Dev (caterer) asking for PO number + dietary list by name, a staff RSVP for the *Winter Party*,
  newsletter, florist quote. Sent: the invitation.
- `~/Documents/Events/Anniversary_Budget_2026.xlsx`: venue, AV, flowers, photographer, gifts filled; Catering row empty;
  Total committed 5,948.00, approved 9,000.00, Remaining 3,052.00 (stale once catering is added).
- Chrome: tab on Hub's login page.

## What each task needs (the reference solution)

**A** (about 80-100 GUI steps): read Martin's rules and the 16 RSVP mails (open the JPG reply card); switch the Hub
event to the anniversary; set 13 rows (10 Attending with 6 plus-one names, 3 Declined: Priya, Ben - his later mail
overrides, Daniel); add Laura Mensah (Attending, in place of Daniel); do not add Marcus Webb; create the folder
"Anniversary RSVPs" and move the 16 RSVP mails (not the Winter-Party one); export the CSV door list (17 people) and save
it as xlsx in Calc; reply to Clara with "23 people" (17 guests + 6 hosts from the event page), door list attached, Cc
Martin, mentioning Marcus Webb's forwarded request.

**B** (about 60-80 GUI steps): from the mails + the hosts table, count 23 diners: canapés 23; beef 8, sea bass 8,
risotto 4, vegan wellington 3; chocolate torte 20, vegan pear 3; drinks package 21, soft-drinks package 2 (Grace,
Owen). Traps: Ben cancelled later, Marcus is not confirmed, Peter Grant's choice + coeliac only in the second mail,
"same for both", vegan vs vegetarian (vegans get the wellington and the vegan dessert), Owen's "no alcohol" only in
Hub, the card's initials, late bites must be removed. Edit PO-2026-0144 (update 6 lines, remove late bites, add 3
lines), check it is charged to the anniversary, submit (total £2,422.57). Budget sheet: Catering PO-2026-0144 /
2,422.57, Total committed 8,370.57, Remaining 629.43. Reply to Dev with PO-2026-0144 and the names David Park (nut
allergy), Peter Grant (coeliac), Hugo Brandt (shellfish), Laura Mensah (gluten-free) (+ vegans).

## Shared live state and expected contention

- **One Hub session in one Chrome.** The Event selector is per session: B opening the Winter Party order 0143 as a
  model (or the Winter Party event) switches A's guest list and CSV export to the Winter Party; A's "Add guest" for
  Laura then defaults to the wrong event, and B's "New purchase order" defaults to whatever A last selected. Guest-list
  filters/pages are shared: B filtering to "Attending" to count diners hides the rows A still has to set, A's search
  box changes B's view. Logging out / re-login kills the other's session.
- **One Thunderbird.** A *moves* the RSVP mails into a new folder while B is reading them in the Inbox (B's selected
  message disappears, B must look in the new folder); both compose drafts (two compose windows, attachment dialogs);
  restarting Thunderbird loses the other's unsaved compose window.
- **LibreOffice**: A's door list and B's budget sheet in the same soffice process.
- No zero-sum element: A edits guests and mail folders; B edits one PO and the budget sheet. A's checker ignores POs and
  B's checker ignores where the mails are (verified in both orders).

## Grading

`evaluate_rsvp` (A) - Hub db (`sql`), mbox folders, door-list xlsx, Drafts with fetched attachment:

| weight | sub-check |
|---|---|
| 0.35 | 13 responding invitees: status and plus-one (name match, empty when none) correct (fraction) |
| 0.05 | no other guest changed (other anniversary invitees, hosts, Winter Party), given >= 1 correct |
| 0.08 | Laura Mensah added to the anniversary as Attending |
| 0.04 | Marcus Webb not confirmed (no Attending row), given >= 1 correct |
| 0.13 | 16 RSVP mails in a folder named "Anniversary RSVPs" and not in the Inbox (fraction; -0.25 if the Winter Party mail was filed there) |
| 0.15 | door list xlsx: 17 expected names (fraction), -0.25 per row for Ben Carter / Daniel Fischer / Priya Natarajan / Marcus Webb |
| 0.10 | draft to the venue with an attached door list holding >= 15 of the 17 names (cross-check) |
| 0.05 | headcount 23 stated |
| 0.05 | Martin in To/Cc and "Marcus Webb" mentioned |

Cap: no correct guest-list response in Hub -> <= 0.3.

`evaluate_catering` (B):

| weight | sub-check |
|---|---|
| 0.45 | the best active Fennel & Fig PO (preferring submitted + anniversary): exact quantity per item over expected ∪ present items (fraction) |
| 0.08 | it is submitted |
| 0.07 | it is charged to the anniversary (and submitted) |
| 0.05 | exactly one active Fennel & Fig order for the anniversary and the Winter Party order untouched (and submitted) |
| 0.07 / 0.03 / 0.02 / 0.03 | budget: catering amount = that PO's total (recomputed from the db) / PO number in the ref cell / total committed / remaining |
| 0.05 / 0.07 / 0.08 | draft to the caterer / contains the PO number / names the 4 guests with allergies or gluten-free needs (fraction) |

Caps: no Fennel & Fig PO charged to the anniversary -> <= 0.3; not submitted -> <= 0.6; line match < 0.7 -> <= 0.6.

## Self-test (offline, node 0, `lib_xtest_x3.py`)

Simulated Guest home, real `app_x3.py` under python3.10 driven over HTTP (event selector, inline guest edits, add guest,
CSV export, PO line edits/adds, submit), Thunderbird emulated on mbox files (folder creation + move with deleted flag,
drafts with attachments), setup run twice. Every page crawled for HTTP 500 under both event selections.

| run | rsvp | catering |
|---|---|---|
| pristine | 0.0 | 0.0 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference) | 1.0 | 1.0 |
| A lazy (missed later mails, reply card and substitute, confirmed the forward, moved 10/16 mails, headcount w/o hosts, no Cc) / B naive (Ben + Marcus counted, no vegan desserts / soft drinks, late bites kept; budget and mail consistent) | 0.48 | 0.60 |
| A Hub only (no mails moved, no door list, no draft) / B new PO instead of Martin's draft (left active), no budget, no mail | 0.52 | 0.60 |

## Provenance

RSVP handling for a corporate client event (replies by email and paper reply cards, plus-ones, substitutions,
forwarded invitations needing approval, door lists and final numbers for the venue) and the matching catering order
(meal choices per guest, dietary labels for the kitchen, PO through the company's purchasing system, event budget
sheet) is a standard office-manager / EA workflow (cf. event-planning checklists and r/EventProduction /
r/Administrative questions on tracking meal choices and dietary requirements from RSVPs).

## Known risks

- The door list may be built by hand with names split into first/last columns or "Last, First" - both accepted; a
  single "Mr & Mrs Park" cell would miss one name.
- An agent that records plus-ones as separate guest rows instead of in the plus-one field fails those response checks
  (the Hub has a dedicated plus-one field on every row).
- Thunderbird's "Move to" on 16 messages is quick with multi-select; drag-and-drop under QEMU can be flaky.
