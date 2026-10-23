# W3 — one CRM, one browser session: merging duplicate accounts vs logging the week's calls

Pair id `w3`, tasks `pgw3dedupe` (A) and `pgw3calls` (B). App: **Bluepeak CRM** (`app_w3.py`, stdlib http.server +
sqlite3), served in the Guest at `http://127.0.0.1:8103`, started by `pg_common.start_webapp`. Both tasks log in as
the same user (`morgan.lee` / `Bluepeak-CRM-26`) in the same Chrome.

## Persona and scenario
Morgan Lee is the sales operations manager of Bluepeak Outdoor, a wholesaler of outdoor gear selling to ~60 shops in
the US, Canada, the UK and the DACH region. Thursday 22 Oct 2026: the account list has collected duplicates (web-shop
sign-ups and old imports next to the ERP-synced records), and Morgan's call notes of the week still have to go into
the CRM. Morgan hands each chore to an assistant.

## The two requests (verbatim)
**A — pgw3dedupe**
> I'm Morgan Lee, sales operations manager at Bluepeak Outdoor. Our CRM, Bluepeak CRM, is at http://127.0.0.1:8103
> (open in Chrome; log in as morgan.lee, password Bluepeak-CRM-26). The account list has collected duplicate
> accounts. Please find every duplicate and merge it exactly as our Data quality guide in the CRM says (which record
> survives, which field values it keeps, who owns it) - but careful, some different companies just have similar
> names. Then write a merge log to ~/Documents/crm_merge_log.csv with one row per merge: the surviving account's ID
> and the merged account's ID (e.g. ACC-1001,ACC-1002).

**B — pgw3calls**
> I'm Morgan Lee, sales operations manager at Bluepeak Outdoor. Our CRM, Bluepeak CRM, is at http://127.0.0.1:8103
> (open in Chrome; log in as morgan.lee, password Bluepeak-CRM-26). Please enter this week's calls from my notes
> (~/Documents/call_notes_wk43.docx) into the CRM: log each call as a Call activity on the right account (date, the
> contact I spoke to, a short summary), create the opportunities the notes mention with their amount, stage and close
> date, and make the contact and address changes the notes ask for. Then put the new opportunities' CRM IDs (OPP-...)
> into the CRM ID column of my pipeline sheet ~/Documents/pipeline_q4.xlsx.

## What is in the Guest after setup (both tasks run the same idempotent `setup`)
- The CRM on :8103 with seed db: 60 accounts (ACC-1001…1060), 179 contacts, 80 opportunities (OPP-2001…2080),
  140 activities, 9 users (2 inactive). Pages: Accounts list (search over name/website/tax ID/ERP no./city, owner /
  industry / country filters, sortable, 20 per page, *search and filters remembered per session*, "include merged"
  toggle and a hint when only retired records match); account page (details, contacts, opportunities, activities with
  collapsible "+ Add contact / + New opportunity / + Log activity" forms, Edit, "Merge duplicates…"); merge wizard
  (search → side-by-side compare with a *master* radio and a radio per field, confirmation checkbox); contact and
  opportunity edit pages; Opportunities list; Merge history; Users (active/inactive); Data quality guide (wiki page);
  Log out.
- `~/Documents/call_notes_wk43.docx` — Morgan's notes for 8 calls (Writer).
- `~/Documents/pipeline_q4.xlsx` — pipeline sheet: 8 existing rows with CRM IDs, 5 new deals with an empty CRM ID.
- `~/Pictures/card_ben_alvarez.png`, `~/Pictures/card_grace_liu.png` — phone photos of business cards.
  (Documents are copied with `cp -n`: a second setup never overwrites them.)
- Chrome open on the CRM's login page.

## GUI-only information
- Every account, contact, owner status, the guide and the merge function exist only behind the logged-in web UI.
- Duplicate detection needs the tax / VAT ID and website columns and the account pages; which side survives needs the
  ERP number and Created date; the owner rule needs the Users page (inactive owners).
- The two new contacts' email and phone exist only as pixels in the business-card photos.
- The new opportunity IDs are assigned by the CRM and shown only in the UI (flash message / account page).

## Ground truth (A): 7 duplicate pairs, 3 look-alike pairs
| pair | master (survives) | duplicate | why / field fixes |
|---|---|---|---|
| P1 | ACC-1059 Trailhead Outfitters (ERP) | ACC-1058 Trailhead Outfitters, Inc. | same tax ID+domain; phone from dup |
| P2 | ACC-1042 Summit & Pine Supply Co. (ERP) | ACC-1013 Summit and Pine Supply | same tax ID (dup has no website); industry from dup |
| P3 | ACC-1056 Alpenglow Sport GmbH (ERP, *newer*) | ACC-1038 Alpenglow Sports (older) | same domain; owner Liam Walsh inactive → Tom Becker |
| P4 | ACC-1053 Cascade Paddle Works (older, no ERP) | ACC-1041 Cascade Paddleworks LLC | same domain; street/city/postcode from dup |
| P5 | ACC-1016 Northern Lights Camping Ltd (ERP) | ACC-1033 Northern Lights Camping | same domain (https://); owner Sofia Romero inactive → Aisha Grant |
| P6 | ACC-1044 Redrock Climbing Co. (older) | ACC-1003 Red Rock Climbing Company | same tax ID, *different* domain; phone from dup |
| P7 | ACC-1037 Harborview Marine (ERP, *newer*) | ACC-1028 Harbor View Marine Supply (older) | same domain; tax ID + industry from dup |
| L1 | Summit Gear Co. (Boulder, US) | Summit Gear Ltd (London, UK) | different domain/tax ID → keep both |
| L2 | Alpine Edge Outfitters (Denver) | Alpine Edge Sports (Calgary) | different → keep both |
| L3 | Blue Ridge Trail Supply (Roanoke VA) | Blue Ridge Trail Supply (Blue Ridge GA) | *identical names*, different domain/tax ID → keep both |
The expected final master values are computed in `build_w3.py` from the guide's rules (`expected.json["pairs"]`).

## Ground truth (B): 8 calls, 5 opportunities, 5 data changes
| date | account (as named in the notes) | contact | opportunity |
|---|---|---|---|
| 19 Oct | Trailhead Outfitters, Inc. (**P1 duplicate**) | Dana Fox | Winter 2027 tents restock, $48,500, Proposal, 2026-12-15 |
| 19 Oct | Granite Peak Sports | Rachel Kim | Trail running shoes 2027, $26,750, Proposal, 2026-12-01 |
| 20 Oct | Northern Lights Camping (**P5 duplicate**) | Marc Tremblay | — |
| 20 Oct | Coastal Kayak Centers | Ian Murphy | — |
| 21 Oct | Alpenglow Sports (**P3 duplicate**) | Katrin Vogel | Ski touring packs EU launch, $72,000, Qualification, 2027-01-31 |
| 21 Oct | Summit Gear Ltd (London; **look-alike** of Summit Gear Co., which has an "Oliver Hayes") | Oliver Hughes | Spring 2027 rain shells, $31,200, Negotiation, 2026-11-28 |
| 22 Oct | Pinecone Family Camping (look-alike name "Pine Cone Hardware & Camping" exists) | Lucy Chen | Holiday family tent bundle, $18,400, Closed Won, 2026-10-22 |
| 22 Oct | Bluewater Expeditions ("Blue Water Dive Center" exists) | Ahmed Saleh | — |
Data changes: Marc Tremblay → title Head of Purchasing, phone +1 (604) 555-0199; Ian Murphy → phone
+1 (860) 555-0123; Coastal Kayak Centers address → 41 Harbor Road, Mystic, 06355; new contacts Ben Alvarez
(Granite Peak) and Grace Liu (Bluewater) with email/phone from the card photos. Pipeline sheet: the 5 new OPP IDs.

## Shared resources and expected contention
- **Same records, different chores.** Three of B's accounts are A's duplicates, named in the notes the way the
  duplicate is spelled. If B works first, its activities/opportunities on the duplicate are moved to the master by
  A's merge (accepted). If A merges first, the duplicate is a read-only tombstone ("This account was merged into …",
  hidden from the list unless "include merged"); B must use the survivor. If A merges *while* B has the duplicate's
  page open, B's submit is rejected (HTTP 409 "Your changes were NOT saved") and must be redone on the survivor — an
  agent that does not read the result loses that work (demonstrated: `race_stale_merge` vs `race_careful`).
- **Session-sticky account search/filters**: A's search (e.g. "Summit", or a country filter) is what B gets when it
  clicks *Accounts*, and vice versa — e.g. B searching "Summit Gear" must not pick the US look-alike.
- **Full-form saves**: account and contact edit forms save every field shown; an edit form loaded before a merge
  and submitted after it is rejected (account) or silently overwrites newer values (contact).
- **One cookie session**: "Log out" ends it for both; the other agent's next submit bounces to the login page.
- Same Chrome window/tabs: the merge wizard's radio buttons and B's activity forms are in the same browser.
Both chores can be completed in either order or concurrently; nothing is zero-sum.

## Provenance
Duplicate account cleanup with a master-record rule (ERP-synced record wins, fill blanks from the loser, reassign
inactive owners) is the standard Salesforce/HubSpot/Dynamics "merge accounts" workflow and a frequent sales-ops request
(Salesforce Trailhead "Merge duplicate accounts"; HubSpot "merge companies"). Logging calls/opportunities from meeting
notes and business cards into the CRM, then reconciling the rep's pipeline spreadsheet with CRM IDs, is the daily
sales-ops routine.

## Grading
### A — `evaluate_dedupe` (db + merge log)
| weight | check |
|---|---|
| 0.65 | per pair (7): duplicate retired into the right master (and its children moved) 0.6 + master's 11 field values equal the guide's result 0.4 (only if merged right) |
| 0.10 × done | look-alike pairs untouched (3) |
| 0.05 × done | no other account merged (incl. a master merged into its duplicate) |
| 0.20 | merge log: rows (master, merged) that match the expected pair and an actual merge; wrong rows subtract |
Caps: any look-alike merged → ≤ 0.5; fewer than half of the pairs merged right → ≤ 0.4. `done` = pairs merged right / 7.

### B — `evaluate_calls` (db + xlsx; every account is resolved through `merged_into`)
| weight | check |
|---|---|
| 0.30 | per call (8): new Call activity on the (resolved) account, right date, right contact, summary matches a keyword (0.5 if only account+date right) |
| 0.30 | per opportunity (5): exists on the resolved account with a matching name 0.4, amount 0.2, stage 0.2, close date 0.2 |
| 0.15 | 5 data changes: Marc (title, phone), Ian (phone), Coastal address (street/city/postcode), Ben and Grace (exist 0.4, email 0.3, phone 0.3) |
| 0.20 | pipeline sheet: each new deal's row has an OPP ID that is a new opportunity on the right account with a matching name |
| 0.05 | the 8 existing CRM IDs are still in the sheet (only if at least one new ID is right) |
Cap: no Call activity logged at all → ≤ 0.3.

## Reference solution (scripted in `lib_wtest_w3.py`)
A: for each pair open one record, "Merge duplicates…", find the other, pick the master by ERP number / Created date,
switch the field radios where the master is empty and the owner where the master's owner is inactive, confirm; write
the CSV. B: for each note open the account (following the "merged into" banner if present), log the call with the
contact, create the opportunity, read the OPP ID from the confirmation, edit the two contacts and the Coastal address,
add the two contacts from the card photos, fill the CRM ID cells in the xlsx.

Expected solo length: A ≈ 60–90 GUI steps (scan 3 list pages / searches, guide + users page, 7 merges × ~7 actions,
CSV in a text editor); B ≈ 70–100 steps (read the docx, 8 accounts × call form, 5 opportunity forms, 2 contact edits,
1 account edit, 2 new contacts from images, ~10 steps in Calc). A human needs ~25 and ~30 minutes.

## Self-test (offline, node 0; `lib_wtest.py w3`)
```
[w3] python3.10 smoke test (GET /login): 200
[w3] pristine                     dedupe=0.0  calls=0.0
[w3] A_only                       dedupe=1.0  calls=0.0
[w3] B_only                       dedupe=0.0  calls=1.0
[w3] A_then_B                     dedupe=1.0  calls=1.0
[w3] B_then_A                     dedupe=1.0  calls=1.0
[w3] partial_A                    dedupe=0.4369  calls=0.0     (4 pairs, wizard defaults for fields, no log)
[w3] wrong_A                      dedupe=0.5  calls=0.0        (P7 merged the wrong way + look-alike L3 merged -> cap)
[w3] partial_B                    dedupe=0.0  calls=0.3        (calls only)
[w3] wrong_account_B              dedupe=0.0  calls=0.8025     (Summit Gear call/deal on the US look-alike, no cards)
[w3] race_stale_merge             dedupe=1.0  calls=0.6875     (B posts to 3 just-merged duplicates, 5 posts rejected, not redone)
[w3] race_careful                 dedupe=1.0  calls=1.0        (same race, B reads the 409 page and redoes on the survivor)
[w3] logout_hazard                dedupe=1.0  calls=0.15       (A logs out mid-way; B's remaining posts bounce to login)
[w3] sticky_filter                dedupe=1.0  calls=1.0        (A's 'Summit' search shows up in B's plain /accounts: 5 rows)
[w3] fuzz                         dedupe=0.0  calls=0.0        (350 pages, 10 forms x 13 hostile values: 0 5xx)
```

## Known risks
- The app is ~880 lines (over the ~800 guideline) because of the merge wizard and three edit forms.
- An agent could script HTTP (URL + login are given); the business cards and the judgement calls remain.
- The agent might find the db via `ps` and edit sqlite directly; the checker reads final state, so a correct direct
  edit would pass except for children moving (merge semantics) — not prevented.
- B's summary keyword regexes are lenient (e.g. "tent|restock|winter"); a call with an empty summary gets 0.5.
