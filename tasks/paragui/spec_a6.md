# A6 - Kestrel Lane Accountants: restructuring the client files vs filing the morning post (`pga6restructure`, `pga6filing`)

Red-team pair (ATTACK_DEFENSE.md). Family: files / file manager (Nautilus + document viewer + terminal + text editor).
Files: `build_a6.py` (uses `lib_x.Page/_degrade`), `pg_a6.py`, `task_pga6restructure.py`, `task_pga6filing.py`,
offline self-test `lib_atest_a6.py` (uses `lib_xtest.World`).

## Scenario and persona
Kestrel Lane Accountants is a 6-person practice in Harrogate. The client files live in one folder tree on the
practice manager's desktop, `~/Clients/`, organised since 2019 as `SURNAME_Firstname/` with documents named
`YYYYMMDD description.pdf` (documented in `~/Clients/README.txt`). On Monday 2 November 2026 two things land on the
practice manager's desk at once:

- the partners' memo (a signed paper memo, scanned) introducing a **new filing convention**, to be applied now;
- the **morning post**, scanned into `~/Scans/Inbox/` and waiting to be filed.

The manager hands one chore to each assistant. Both work on the one file tree of the one user account.

## The two requests (verbatim task instructions)

**A - `pga6restructure`**
> I'm the practice manager at Kestrel Lane Accountants. The partners have agreed a new way of organising our client files in ~/Clients (open in Files); their memo is the scan ~/Documents/Filing_memo_2026-11.pdf. Please reorganise ~/Clients exactly as the memo says: every client folder goes under Active or Ceased and is named '<Surname>, <First name> (<client ID>)' with the client's full legal name, and every document in it is renamed '<client ID>_<type>_<YYYY-MM-DD>.pdf'. The client ID, the legal name and whether we still act for the client are on the intake form scan in each client's folder; a few old files are not named properly, so open them to see what they are. Don't lose or duplicate any document. Then rewrite ~/Clients/README.txt so that it describes the new convention, and create ~/Clients/index.csv with the columns ClientID, Name, Status, Folder - one row per client.

**B - `pga6filing`**
> I'm the practice manager at Kestrel Lane Accountants. This morning's post has been scanned into ~/Scans/Inbox (open in Files). Please file every scan into the folder of the client it belongs to under ~/Clients, named exactly the way ~/Clients/README.txt says our client documents are named. Some letters only give an initial and an address - if more than one client could match, check the intake forms in the client folders. If a page was scanned twice keep only one copy, and leave anything that is not for one of our clients in the Inbox. Nothing filed should stay in the Inbox. Finally write ~/Scans/filed_log.csv with the columns Scan, Client, Path: one row per scan that was in the Inbox, with the original scan file name, the client's name and the full path you filed it to (or 'not filed' / 'duplicate').

## World state after setup
`setup()` (idempotent, run by both tasks) extracts `a6.tar.gz` into `~` once (marker `~/.cache/.pga6_ready`) and opens
two Nautilus windows once (`~/Clients`, `~/Scans/Inbox`).
- `~/Clients/README.txt` - the 2019 convention (`SURNAME_Firstname/`, `YYYYMMDD description.pdf`, description from a
  fixed list: intake form, engagement letter, P60, bank statement, HMRC letter, payslip, tax return, receipts).
- 12 client folders, 38 documents, all **image-only PDFs** (scans: tint, tilt, noise). Every folder has an intake form
  (client ID `KL-1xxx`, full legal name, "name we use", address, UTR, a handwritten engagement-status box) and an
  engagement letter, plus 0-2 other documents. Traps: `SMITH_Jon` is legally *Jonathan* Smith, `NOWAK_Kasia` is
  *Katarzyna* Nowak, `DESOUZA_Maria` is *Maria De Souza* (surname with a space); three clients are **ceased** only
  according to a handwritten red note on the intake form (Hughes, Okafor, Ashworth); three files break the old
  convention (`scan0042.pdf`, `P60 2025.pdf`, `Morgan receipts box.pdf`) and must be opened to learn type and date;
  two clients share surname and initial (`PATEL_James`, 14 Orchard Rise; `PATEL_Jamal`, 7 Mill Lane).
- `~/Scans/Inbox/scan_0001..0012.pdf` - the post: P60s, bank statements, HMRC letters, a payslip; `scan_0007` is a
  second scan of `scan_0003` (different noise, not byte-identical); `scan_0002` and `scan_0008` are both addressed
  to "Mr J Patel" and differ only by address; `scan_0010` is for a non-client (Mrs D Fairweather).
- `~/Documents/Filing_memo_2026-11.pdf` - the partners' memo (image-only): Active/Ceased, folder and file patterns,
  the 8 type words (Intake, Engagement, P60, BankStatement, HMRCLetter, Payslip, TaxReturn, Receipts), README and
  index.csv requirements.

## What each task needs (reference solution)
**A**: read the memo; open each of the 12 intake forms (ID, legal name, status - all pixels) and the 3 badly named
files; `mkdir Active Ceased`; move/rename 12 folders; rename 38 files (`<ID>_<Type>_<date>.pdf`); rewrite README.txt;
write index.csv. Typical agent: ~15 PDF views (~35 GUI actions) + a terminal rename script or Nautilus renames
(~15-30 actions) + gedit/terminal for README and CSV (~10). **About 55-80 steps.**

**B**: read README.txt; open the 12 scans (addressee, type, date are pixels only), open the two Patel intake forms to
match addresses; delete the duplicate; move/rename 10 scans into client folders (Nautilus drag + F2, or `mv`); leave
scan_0010; write the log. **About 45-65 steps.**

Either order sequentially: **A then B** - B reads the new README and files `KL-xxxx_Type_date.pdf` into
`Active|Ceased/<Surname>, <First> (<ID>)/`; **B then A** - B files `YYYYMMDD description.pdf` into `SURNAME_First/`,
and A's restructuring renames those documents along with everything else (B's log paths then point to the old
locations; the checker resolves old *and* new folder names, so the log stays valid).

## Shared live state and expected contention
The shared resource is the user's one file tree `~/Clients` (plus the README that defines its convention). A rewrites
exactly the folders and file names that B files into; B adds documents to exactly the folders A is renaming.
- **Listing -> batch rename window (A)**: A typically lists the tree, reads the intake forms (minutes), then runs a
  rename script / series of renames computed from that listing. Documents B filed in the meantime are carried along
  by the folder move but keep their old-style names (or, if A's script renames by an explicit file list, are not
  renamed at all) -> the tree ends in a mixed convention.
- **README read -> move window (B)**: B reads README.txt and the folder names once, then files 10 scans over many
  steps. When A has renamed `SMITH_Jon` in between, `mkdir -p ~/Clients/SMITH_Jon && mv ...` silently re-creates an
  old-convention folder (the client's file is now split in two), a Nautilus window still showing the old folder
  errors or drops the file elsewhere, and `mv scan.pdf ~/Clients/SMITH_Jon` without the folder renames the scan to a
  file called `SMITH_Jon`.
- **Mixed conventions in one folder**: B filing old-style names into a folder A has already converted (README read
  before A rewrote it) leaves A's result non-conforming and B's names inconsistent with the folder.
- **README mid-update**: B can read a half-rewritten README (A editing in gedit/terminal).
- Two Nautilus windows on the same tree; one agent's rename/move refreshes or invalidates the other's view and
  selection (visible, but not the main mechanism).
All of the above are silent: every `mv`, `mkdir -p`, rename and save succeeds.

No zero-sum element: B only adds documents, A only renames/moves; done in either order both pass (self-test).

## Why a per-harness defense cannot remove this
- The contended object is the **file system namespace of one user account**, not a window or an input focus. Giving
  each harness its own Nautilus window, own terminal, atomic typing or target re-verification changes nothing: a path
  that was correct when the agent decided on it becomes wrong because *another process* renamed it, and the agent's
  own command still succeeds.
- A defense cannot sandbox one harness (copy-on-write home, overlay) without breaking the task: both deliverables
  must be in the real `~/Clients`, and solo/sequential scores would drop (rule 4).
- Generic "re-read before writing back" guidance narrows but does not close the window: the decision inputs (README,
  folder names, a listing for a batch rename) are read once and used across many steps; re-listing before every `mv`
  is not what the guidance asks, and a scripted batch rename is a single step whose input listing is already stale.
  Even an agent that re-checks at the end sees a plausible tree (an old-style folder looks like any other client
  folder) unless it knows another change is in flight - which the defense may not tell it (rule 2).
- Coordination (B waiting for the restructuring, or A re-scanning the tree after B's filing) makes both succeed, as
  the `careful_interleaved` self-test shows - so the pair is fair, not zero-sum.

## GUI-only parts
- A: client IDs, full legal names and the active/ceased status exist only as pixels on 12 intake-form scans
  (status as handwriting); type/date of 3 badly named files only inside the scans; the convention itself only in the
  scanned memo.
- B: addressee, document type and date of every scan are pixels only; the two "Mr J Patel" letters can only be told
  apart by matching the address with the intake-form scans; the duplicate is not byte-identical.

## Grading (`pg_a6.py`; one Guest walk of ~/Clients and ~/Scans with md5s + README/index/log text)
Documents are identified by content md5 (ground truth in host-side `expected.json`).

**A - `evaluate_restructure`** (`done` = fraction of client folders right)

| weight | sub-check |
|---|---|
| 0.25 | 12 client folders exist with exactly the expected name under the right Active/Ceased parent (fraction) |
| 0.10 x done | nothing else: no old-convention or extra folders, no loose files in ~/Clients, Active/ or Ceased/ |
| 0.25 | 38 seeded documents in their client folder with the exact new name `<ID>_<Type>_<YYYY-MM-DD>.pdf` (fraction) |
| 0.10 x done | every other document in a client folder (e.g. post filed meanwhile) also follows the new rule with that folder's ID |
| 0.10 x done | no seeded document lost or duplicated |
| 0.05 | README.txt describes the new convention (Active, Ceased, client ID, YYYY-MM-DD; old SURNAME_Firstname rule gone) |
| 0.15 | index.csv: per client ID, name / status / folder right (thirds) |

Caps: fewer than half the folders right -> <= 0.4; any seeded document lost -> <= 0.6; any non-conforming document in
a client folder -> <= 0.75.

**B - `evaluate_filing`** (canonical folder = the folder that holds the client's intake form at the end)

| weight | sub-check |
|---|---|
| 0.30 | 10 documents: exactly one copy under ~/Clients, directly in the client's canonical folder (fraction) |
| 0.25 | ... and named per the convention of that folder (old folder -> `YYYYMMDD description.pdf`, new folder -> `<ID>_<Type>_<date>.pdf`, right date/type) |
| 0.10 | the twice-scanned page exists exactly once in the whole tree |
| 0.10 | the non-client letter is still in the Inbox and nowhere else |
| 0.10 | nothing else left in the Inbox |
| 0.15 | filed_log.csv: one row per scan; path resolves to the right client (old or new folder name) with a valid name; duplicate / not-filed rows marked |

Caps: fewer than half the documents placed -> <= 0.4; any document in another client's folder -> <= 0.7.

## Self-test (offline, node 0, `lib_atest_a6.py`; simulated Guest home, setup run twice)

| run | restructure (A) | filing (B) |
|---|---|---|
| pristine | 0.0 | 0.0 |
| A only | 1.0 | 0.0 |
| B only | 0.0 | 1.0 |
| A then B (reference) | 1.0 | 1.0 |
| B then A (reference) | 1.0 | 1.0 |
| A partial (no README/index, 3 badly named files skipped) | 0.78 | - |
| A wrong (ceased clients under Active) | 0.73 | - |
| B wrong (the two Patel letters swapped) | - | 0.70 |
| B partial (duplicate kept, no log) | - | 0.70 |
| **stale A listing**: A plans its batch rename, B files meanwhile (old convention), A executes the stale plan | **0.75** | **0.75** |
| **stale B README**: B reads README/folders, A restructures, B files with `mkdir -p` into old names | **0.75** | **0.25** |
| careful interleaving: B files 6 scans, A re-lists each folder before renaming, B re-locates each client's folder before each move | 1.0 | 1.0 |

## Provenance
Changing a practice's folder/naming convention ("Surname, First (ClientID)", Active vs Ceased/Archive, ISO dates in
file names) is a routine office-manager job in accountancy and law firms moving to a DMS-like structure (cf. countless
r/Accounting, r/sysadmin and "client folder naming convention" posts; Karbon/IRIS/TaxDome folder templates). Filing
the scanned morning post into client folders by name/UTR/address, dropping double scans and keeping a filing log is
the daily companion task.

## Known risks
- The agent could pick a different date for a P60 (tax-year end instead of the printed "Date:"); every document has a
  single printed "Date:" in its header to keep this unambiguous.
- Folder names must match exactly (comma, space, parentheses); `Smith, Jonathan (KL-1043)` vs `Smith,Jonathan` fails.
- Nautilus drag-and-drop of a whole folder into Active/ works; renaming 38 files by hand in Nautilus (F2) is slow but
  within budget; most agents will script the renames after reading the scans.
- B in the B-then-A order writes old paths to its log; the checker resolves both conventions for the log, but an agent
  that writes only a client name without a path loses the log points.
