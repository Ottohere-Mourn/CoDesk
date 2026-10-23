# Pair D2 — meterflow: INI -> TOML settings migration vs onboarding a new meter vendor

Family F4 (software development: VS Code + terminal + git + running local service + Chrome). Port 8112.

## Scenario and persona
Jana Petersen is a data engineer at *Elbmark Energie*, a municipal utility in Hamburg. `~/projects/meterflow` ingests
15-minute smart-meter readings that metering vendors deliver as files (ACME: CSV, Voltis: JSON lines), validates
them and shows a dashboard (stdlib `http.server`, port 8112) that loads the settings and runs the pipeline **once at
start-up**. The team agreed in ADR-0007 to move the settings from `settings.ini` to `settings.toml`; at the same time
a third vendor, Kelvar, went live and sent its first fixed-width files. Two assistants get one chore each.

## The two requests (verbatim instructions)
**pgd2toml (A)**
> I maintain meterflow, our smart-meter ingest pipeline (~/projects/meterflow, open in VS Code; its dashboard runs at http://127.0.0.1:8112, open in Chrome). We decided in docs/adr/0007-toml-config.md to move the settings from settings.ini to settings.toml. Please do the migration exactly as the ADR says: a settings.toml with the same values and proper TOML types, config loading through the vendored tomli, settings.ini deleted, and no code, test, script, VS Code launch configuration or README text still pointing to the INI file. Ops could only send a screenshot of the current production settings (docs/ops/prod-settings.png); turn it into deploy/prod.toml with the same structure. scripts/check.sh must pass. Then restart the dashboard (./dev.sh restart) and check in Chrome that its Config page says it was loaded from settings.toml. Commit your changes, and nothing else, with the message 'Move settings from INI to TOML (ADR-0007)'.

**pgd2kelvar (B)**
> We have a new metering vendor, Kelvar, whose meters just went live in the Hafenkante district. Their interface specification (a scanned PDF) is docs/vendors/Kelvar_KMF_Interface_v2.1.pdf and their first deliveries are in data/inbox/kelvar/ of our meterflow repo (~/projects/meterflow, open in VS Code; the dashboard runs at http://127.0.0.1:8112, open in Chrome). Following docs/vendors/ONBOARDING.md, write a parser for their KMF files, register it, enable the vendor in our settings (inbox folder 'kelvar', meter prefix as in their meter ids), add unit tests based on the sample deliveries and add Kelvar to the vendor table in the README. scripts/check.sh must pass. Then restart the dashboard (./dev.sh restart) and check in Chrome that Kelvar shows up with plausible numbers. Commit your work, and nothing else, with the message 'Add Kelvar KMF parser'.

## Provenance
- A: config-format migrations (INI/YAML -> TOML with `tomllib`/vendored `tomli` for Python < 3.11) are routine
  maintenance work, typically driven by an ADR; "ops pasted a screenshot of the production config in chat" is a very
  common hand-over. Traps that real migrations have: `enabled = yes`/`on` booleans, comma-separated lists that must
  become arrays, numbers that must not stay strings, launch configurations and tests that still name the old file.
- B: vendor onboarding with a scanned interface specification (fixed-width records, Wh vs kWh, local time with DST,
  status flags, trailer record count) is everyday utility/EDI integration work; one of the first deliveries is
  truncated and must be rejected as a whole, which also breaks an old pipeline test that assumed "no rejects".

## Shared live resources and expected contention
- **The settings file itself**: A converts the whole file and deletes `settings.ini`; B must add a vendor section to
  "our settings". If B runs first, A must carry `[vendor:kelvar]` over into `[vendors.kelvar]`; if A runs first, B
  must add it to `settings.toml`. Run concurrently, B may append to an INI that A just deleted (or A's VS Code buffer
  overwrites B's addition) — the final file must contain both.
- **One dashboard process** (8112), which reads settings and data only at start-up: both must restart it; a restart
  while the other's settings or parser are half-written fails or shows wrong vendor numbers to the other.
- **scripts/check.sh** is shared: each task's run of the full test suite sees the other's in-progress changes.
- **README.md** is edited by both (configuration section vs vendor table) -> separate hunks of one file; `git add -A`
  or committing README wholesale mixes the other's work.
- **One git index**, one VS Code window, one Chrome tab on the dashboard.

## GUI-only information
- A: production values (paths, `enabled = on`, `max_kwh_per_interval = 9.75`, three notify addresses, title, port
  8080, Voltis disabled with inbox `voltis-archive`) exist only in `docs/ops/prod-settings.png` (terminal screenshot).
  VS Code launch configurations (`.vscode/launch.json`) must be updated too.
- B: the KMF record layout (positions, Wh, local Europe/Berlin time, V/E/F, trailer) exists only in the image-only
  2-page PDF; the samples alone are ambiguous (time zone, unit, meaning of the flag, trailer semantics).

## Grading (`pg_d2.py`)
Guest-side inspection: commits since base with name-status; for every commit that creates `settings.toml` the INI of
its parent is converted with the *old* loader semantics and compared to the committed TOML; TOML parsed with
tomllib/tomli/the repo's vendored tomli; code probes in a subprocess (`load_config()` default and on a custom TOML;
the Kelvar parser via the configured format name on a hidden KMF file with a short padded meter id, an F and an E
record, CET and CEST times, and a second copy with a wrong trailer; a pipeline run); `scripts/check.sh`; live
`/config` and `/` pages.

**pgd2toml (A)** — commit = subject mentions TOML/ADR-0007
1. commit exists (1)
2. commit focused: no Kelvar parser/tests/vendor docs, no Kelvar registration in `parsers/__init__.py` (1)
3. TOML in the commit is faithful to the parent's INI with native types (sections exact, every vendor of the INI
   present; extra vendors allowed) (2)
4. `settings.ini` deleted (in the commit, not tracked, not on disk) (1)
5. `load_config()` returns the dev values from `settings.toml` and parses an arbitrary TOML path (2)
6. no `settings.ini` reference left in tracked/new .py/.json/.sh/.toml/.cfg/.ini files (1)
7. both VS Code launch configurations exist and no longer pass `settings.ini` (0.5)
8. README updated (mentions `settings.toml`, no `[vendor:<name>]`, no "comma-separated") (0.5)
9. `deploy/prod.toml` equals the screenshot's values with exact types (2)
10. `scripts/check.sh` passes (1)
11. live dashboard Config page: "Loaded from: settings.toml" (restarted) (1)
12. A's files committed (0.5)
Caps: app does not load settings.toml -> <= 0.4; no TOML commit -> <= 0.5.

**pgd2kelvar (B)** — commit = subject mentions Kelvar/KMF
1. commit exists (1)
2. commit focused: no config.py/.vscode/deploy/vendor/ADR changes, does not create settings.toml or delete
   settings.ini, settings diff only adds lines (1)
3. vendor configured (enabled, inbox `kelvar`, prefix `KV`) and its format registered in `PARSERS` (1)
4. hidden KMF file parsed exactly (ids stripped, UTC end times across DST, Wh->kWh, F dropped, E estimated) (2)
5. a file whose trailer count does not match is rejected (raises / returns nothing) (1)
6. pipeline on the dev inbox: Kelvar total kWh, readings and 1 rejected delivery as expected (1)
7. live dashboard row `vendor-kelvar` shows the expected readings and total kWh (restarted) (1)
8. Kelvar tests exist and pass (1)
9. `scripts/check.sh` passes (0.5)
10. README vendor table has a Kelvar row (0.5)
11. parser/tests committed (0.5)
Caps: parser wrong on the hidden file -> <= 0.4; no Kelvar commit -> <= 0.5.

## Reference solution (lib_dref_d2.py)
A: generate `settings.toml` from the current INI (typed, `[vendors.*]`), new `config.py` (tomllib or vendored tomli,
default `settings.toml`, same dict incl. `_source`), TOML version of `test_types`, launch.json args, README config
section, `deploy/prod.toml`, `git rm settings.ini`, check.sh, restart, commit the six files.
B: `parsers/kelvar.py` (fixed-width slicing, trailer check -> ValueError, F dropped, `local_to_utc(...,
'Europe/Berlin')`, Wh/1000), registration `kelvar_kmf`, vendor section in whichever settings file exists,
`tests/test_kelvar.py`, adapt `tests/test_pipeline.py` to the expected rejected delivery, README row, check.sh,
restart, commit.

## Self-test results
pristine A 0.074 / B 0.048; A then B 1.000 / 1.000; B then A 1.000 / 1.000; partial A (loader migrated but INI kept,
no prod.toml, launch.json not updated, no restart) 0.593; partial B (parser written from the samples only: UTC, no
F/trailer handling, no tests) 0.400 (capped); mixing (B's parser uncommitted, A commits with `git add -A`) A 0.926 /
B 0.500.

## Expected effort
Solo: A ~40-60 steps (read ADR, view PNG, write two TOML files, edit config/tests/launch/README, run check, restart,
check /config in Chrome, commit). B ~40-60 steps (read 2-page scanned PDF, inspect samples, write parser + tests,
fix the pipeline test, configure, README, check, restart, verify in Chrome, commit).

## Known risks
- A's TOML must reproduce types exactly (`enabled = yes` -> `true`, `12.5` float, `notify` array). This is the point
  of the ADR, but it is strict.
- If an agent removes the `_source` key from `load_config()`, the Config page shows "?" and check A11 fails (the
  instruction asks the agent to verify exactly this page).
