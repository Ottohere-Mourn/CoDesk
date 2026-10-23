# X4 - Research-group admin after a conference (`pgx4claims`, `pgx4pubs`)

Family F6 (cross-application workflows). Files: `build_x4.py`, `app_x4.py`, `pg_x4.py`, `task_pgx4claims.py`,
`task_pgx4pubs.py`, self-test `lib_xtest_x4.py`; shared helpers `lib_x.py`, `pg_xcommon.py`, `lib_xtest.py`.

## Scenario and persona

Jamie Ross is the lab manager of two research groups in the School of Informatics, University of Northbridge (UK):
the **Marsh Lab** (Prof. Elena Marsh, vision & learning) and the **Okafor Lab** (Dr Chidi Okafor, language agents).
Group administration runs through **LabDesk**, the School's intranet portal: expense claims (lines in the receipt's
currency, converted to GBP with Finance's FX table for the receipt date, charged to a grant, submitted -> CLM number),
the groups' publication records (they feed the public group pages), members with their default grants, grants, FX
rates. It is Monday 5 October 2026. Four members are back from ECCV 2026 in Malmö (7-12 Sep) and have emailed their
receipts; in the same weeks several papers were accepted. Elena asks Jamie for two things, handed to two assistants:

- the **ECCV travel claims** (Elena's "ECCV claims" mail, Finance's policy extract);
- the **publication lists** (Elena's "Website publications update" mail).

Shared desktop: one Thunderbird (jamie.ross@northbridge.ac.uk, offline POP profile), one Chrome with LabDesk (both
log in as `jross`), LibreOffice, VS Code opened on the website repo, a terminal.

## The two requests (verbatim task instructions)

**A - `pgx4claims`**
> Please do the ECCV 2026 travel expense claims Elena asked for (her email 'ECCV claims' in Thunderbird); the receipts
> are in the travellers' emails and the rules are in the policy that School Finance emailed. In LabDesk
> (http://127.0.0.1:8124, username jross, password Northbridge#26) create and submit one claim per traveller, with a
> line for each reimbursable receipt in the receipt's own currency and date, applying the policy's caps and exclusions.
> File every traveller's receipt email into a new mail folder Claims/ECCV 2026. Then fill in
> ~/Documents/Lab/ECCV2026_travel_summary.xlsx (claim number and GBP total per traveller, totals per grant) and leave a
> draft to finance-claims@inf.northbridge.ac.uk listing the claim numbers with their GBP totals. Leave it in Drafts -
> don't send it.

**B - `pgx4pubs`**
> Elena wants our publication lists brought up to date - see her email 'Website publications update' in Thunderbird.
> Using the acceptance emails, camera-ready PDFs and arXiv notice in the mailbox, add or update every new paper of both
> groups in LabDesk's Publications (http://127.0.0.1:8124, username jross, password Northbridge#26) with the exact
> title, authors in order, venue, year and arXiv id; add the Marsh Lab papers to the website repo
> ~/projects/marsh-lab-website (_bibliography/papers.bib, following its README) and commit; then leave an announcement
> draft to ml-groups@lists.northbridge.ac.uk listing the new papers. Nothing that was rejected should appear anywhere.
> Leave the announcement in Drafts - don't send it.

## World state after setup

- **LabDesk** (`app_x4.py`, port 8124, db `~/.local/share/intranet/labdesk/app.db`): 2 groups, 10 members with default
  travel grants, 5 grants, daily FX rates (EUR/SEK/USD, working days May-Oct 2026, weekends use the previous rate),
  8 historical claims CLM-2026-0131..0138, 13 publication records (8 Marsh incl. the arXiv preprint of the NeurIPS paper,
  5 Okafor). Header **Group selector** (Marsh / Okafor), stored in the login session (defaults to Marsh at login):
  scopes the claims list, the traveller list of "New claim", the publications list, the members page and the default
  group of a new publication. List filters (status/search/year/type/page, FX month) are also per session. Claim page:
  add/remove lines (date, category, description, currency, amount -> rate and GBP shown), change grant, submit
  (number assigned), return to draft. Activity log.
- **Thunderbird** Inbox (13 mails): Tomás (one 4-page scanned PDF: ECCV registration paid on the School card, BA e-ticket
  incl. £24 seat selection, hotel 5 nights at SEK 1,950 + minibar, dinner with 2 glasses of wine; plus the NeurIPS
  camera-ready PDF - new title, extra author), Aisha (scanned BA confirmation + phone photos of hotel, lunch and dinner on
  the same day; says Elena wants the ERC grant), Aisha's follow-up with the train-ticket photo, Ben (photos: taxi and a
  pharmacy receipt for sun cream/toothpaste), Priya (Okafor Lab; scanned PDF: SAS ticket, hotel 3 nights at SEK 2,100,
  dinner incl. a beer; plus the EMNLP Findings camera-ready and the arXiv id in the text), Wei (AAAI rejection - do not
  list), Elena's forward of the WACV acceptance (title + authors), Lena's arXiv announcement, Finance's reminder with
  the policy extract PDF (caps: hotel SEK 1,800/night, subsistence SEK 650/day; alcohol, seat selection, insurance,
  personal items excluded; registration on the School card not claimable), Elena's two requests, distractors.
  Folders: Claims (with Claims/BMVC 2025 from last year), Sent.
- `~/Documents/Lab/ECCV2026_travel_summary.xlsx` (template: traveller rows, grant-total rows),
  `~/projects/marsh-lab-website` (git repo, 2 commits; README with the BibTeX key/field conventions; papers.bib with
  8 Marsh entries incl. `ruiz2026sparse` as an arXiv @article), VS Code opened on it; Chrome on LabDesk's login page.

## What each task needs (the reference solution)

**A** (expected values): read the policy and Elena's rules, open 5 receipt mails (2 scanned PDFs, 1 scanned
confirmation, 6 phone photos). Claims: Tomás (Marsh, EP/X031452/1): GBP 262.40 (fare+taxes, without seat selection),
SEK 9,000 (5 x 1,800 cap, minibar out), SEK 570 (dinner without wine), registration not claimed. Aisha (Marsh,
ERC-101115274 - not her default): GBP 241.90, SEK 6,600, SEK 650 (meals 185 + 690 on 10 Sep capped; the
non-alcoholic beer counts), SEK 125 train. Ben (Marsh, ERC default): SEK 380 taxi only (pharmacy = personal). Priya
(Okafor, EP/Y004117/1 - switch the Group selector to see her): GBP 312.75, SEK 5,400 (3 x 1,800 cap), SEK 445 (dinner
without beer). Submit all four (CLM-2026-0139..0142 in the reference; GBP totals 992.10 / 804.24 / 28.97 / 758.44 with
the receipt-date rates). File the 5 receipt mails into the new folder Claims/ECCV 2026. Fill the summary (4 rows,
grant totals EP/X031452/1, ERC-101115274 = Aisha + Ben, EP/Y004117/1) and draft the Finance mail with the 4 numbers and
totals. About 80-100 GUI steps (11 claim-line forms, 4 claims, reading 14 receipt images).

**B**: read Elena's mail; open the two camera-ready PDFs (attached to Tomás's and Priya's receipt mails - possibly
already moved to Claims/ECCV 2026 by A), the WACV forward and the arXiv announcement; ignore Wei's rejected paper.
LabDesk: edit the existing preprint record of the NeurIPS paper (new title "Sparse Prompt Tuning for Open-Vocabulary
Semantic Segmentation", authors Ruiz, Rahman, Zhang, Marsh, venue NeurIPS 2026, keep arXiv 2605.08812); add "Few-Shot
Scene Graph Generation with Relation Priors" (WACV 2027, year 2027) and "Benchmarking Monocular Depth Foundation Models
under Adverse Weather" (preprint, arXiv 2609.15502) to Marsh Lab; switch to Okafor Lab and add "Calibrated Refusals
for Tool-Using Language Agents" (Findings of EMNLP 2026, arXiv 2609.11873). Website repo: turn `ruiz2026sparse` into
an @inproceedings with the NeurIPS booktitle and new title/authors, add `carter2027fewshot` and
`vogel2026benchmarking` per README (no Okafor paper, nothing rejected), commit only papers.bib. Draft the announcement
to the list with the four titles. About 60-80 GUI steps.

## Shared live state and expected contention

- **One LabDesk session in one Chrome.** The Group selector is a session setting. A must switch to Okafor Lab for
  Priya's claim while B adds Marsh papers - B's "Add publication" form then defaults to Okafor Lab (a paper silently
  lands in the wrong group) and B's publication list suddenly shows the other group; when B switches back to Marsh for
  the WACV paper, A's "New claim" traveller list no longer contains Priya, A's claims list loses her claim. List filters
  (search, status, year, page) are shared too. Logging out kills the other agent's session.
- **One Thunderbird.** A moves the five receipt mails into Claims/ECCV 2026 - two of them carry B's camera-ready PDFs,
  so B has to find them in the new folder (or loses an opened message when it disappears from the Inbox). Both open
  attachments from the same messages, both compose drafts (two compose windows). Restarting Thunderbird kills the
  other's compose window.
- **Desktop**: A works in LibreOffice Calc and image/PDF viewers, B in VS Code/terminal on the repo; focus switches and
  long typed commands interleave.
- No zero-sum element: A only creates claims and moves mails; B only edits publication records, the repo and its own
  draft. Each checker accepts the other's changes (verified in both orders; B's reference reads the camera-readies from
  wherever the mails are).

## Grading

`evaluate_claims` (A) - LabDesk db via `sql`, mbox via `MAILX`, workbook fetched:

| weight | sub-check |
|---|---|
| 0.60 | per traveller (4 x 0.15, six equal parts): a new claim exists for the member; right grant; submitted with a number; GBP lines sum; SEK lines sum (policy caps/exclusions applied); no EUR/USD line (registration not claimed) and GBP total within 1% of the expected total (receipt-date rates) |
| 0.05 | no extra claims (duplicates or other members) |
| 0.07 | the 5 receipt mails are in a folder `.../Claims/ECCV 2026` and not in the Inbox (fraction) |
| 0.08 / 0.04 | summary workbook: traveller rows carry the LabDesk claim number / the claim's GBP total (cross-checked with the db) |
| 0.04 | grant-total rows (code + summed totals of the db claims), 3 grants |
| 0.06 / 0.06 | draft to finance-claims@ lists the claim numbers / the GBP totals (fractions) |

Caps: no submitted claim -> <= 0.3; workbook missing -> <= 0.75; any traveller with wrong amounts (policy not applied)
-> <= 0.7.

`evaluate_pubs` (B) - LabDesk db, repo (git log base..HEAD, status, HEAD and working-tree papers.bib), mbox:

| weight | sub-check |
|---|---|
| 0.40 | per paper (4 x 0.10): a live record with exactly the camera-ready/arXiv title in the right group (0.04), venue + year (+ type Preprint for the arXiv paper) (0.03), authors in order (0.02), arXiv id (0.01) |
| 0.05 | hygiene: exactly one record for the NeurIPS paper (preprint updated, not duplicated), rejected paper not listed, no seeded record removed |
| 0.21 | papers.bib entries `ruiz2026sparse`, `carter2027fewshot`, `vogel2026benchmarking` (4 parts each: title, author order, year + venue/booktitle (+ @inproceedings for conference papers), arXiv id) |
| 0.04 | bib hygiene: all 8 seeded keys kept, no duplicate keys, no Okafor/rejected entry |
| 0.05 / 0.05 | new commits touch only papers.bib / the bib changes are committed (HEAD == working tree, contains the WACV key) |
| 0.16 / 0.04 | announcement draft to ml-groups@ names the 4 titles (fraction) / does not mention the rejected paper |

Caps: no new paper in LabDesk -> <= 0.4; papers.bib missing/unparsable -> <= 0.6; the rejected paper listed anywhere
(LabDesk, bib, announcement) -> <= 0.6.

## Self-test (offline, node 0, `lib_xtest_x4.py`)

Simulated Guest home, `app_x4.py` under python3.10 driven over HTTP (login, group switches, claim/line/submit forms,
publication forms, crawl of 17 pages under both group settings without errors), Thunderbird emulated on the mbox files
(tb_move + drafts), git run in the fake repo, setup run twice (idempotent).

| run | claims | pubs |
|---|---|---|
| pristine | 0.0 | 0.0175 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference) | 1.0 | 1.0 |
| A sloppy (registration + full hotel + wine claimed for Tomás, Aisha on default grant and meals uncapped, Ben's pharmacy claimed, mails not filed) / B dup (NeurIPS paper added as a second record, rejected paper added and announced, wrong key `carter2027few-shot`, nothing committed) | 0.7 | 0.6 |
| A claims left as drafts, nothing else / B with the shared Group selector on Okafor (two Marsh papers in the wrong group, swapped author order for the EMNLP paper), no announcement | 0.3 | 0.7 |

## Provenance

Reimbursing conference travel against a university expenses policy (overseas accommodation and subsistence caps,
alcohol and personal items excluded, registration paid centrally, conversion at the finance rate, charging the right
grant) is a routine task of research administrators and PhD students (cf. typical UK university T&E policies and the
recurring academia.stackexchange questions about per-diem caps and reimbursing alcohol). Keeping a group's publication
list in sync - updating an arXiv entry once accepted, al-folio/Jekyll `papers.bib` with key conventions, and
announcing new papers on the group list - is the standard lab-website chore.

## Known risks

- The `<input type=date>` in Chrome is typed in the locale order (mm/dd/yyyy on an en-US Guest); a mistyped date
  changes the FX rate - only the 1% total tolerance and the line amounts depend on it.
- Agents may split Aisha's capped meals into two lines (185 + 465) - accepted (per-currency sums).
- Text-PDF camera-readies are copyable; the receipts are pixels only (scans/photos) and must be read visually.
- BibTeX checking is regex/brace based; exotic formatting (strings, @preamble) is not expected in this small file.
