# Pair D4 — shorebirds: reproduce the paper's Table 2 vs cut release 1.4.0

Family F4 (software development: VS Code + terminal + git + running local service + Chrome). Port 8114.

## Scenario and persona
The Wadden Lab (Kiel) keeps its survey-analysis code in `~/projects/shorebirds`: survey sheets `data/counts_<year>.csv`,
`python3 -m shorebirds.run_all` regenerates `results/table2.csv` and `results/fig2_trends.svg` (Table 2 / Figure 2 of
the paper), and a lab report server (8114) runs the analysis **once at start-up** and shows Table 2, Figure 2 and a
footer with the package version and Zenodo DOI. Since v1.3.0 four changes were merged (#41, #43, #45, #46); #45 (a
"faster aggregation") silently broke the effort correction, and the 2026 sheet from the new field app has a different
column order, so `run_all` crashes. The paper (draft v3, scanned) was submitted with the correct numbers. PhD student
Noor wants Table 2 fixed; PI Femke wants release 1.4.0 out for the submission. Two assistants, one each.

## The two requests (verbatim instructions)
**pgd4table (A)**
> I'm Noor, a PhD student in the Wadden Lab. Our analysis package is in ~/projects/shorebirds (open in VS Code) and the lab's report page runs at http://127.0.0.1:8114 (open in Chrome). 'python3 -m shorebirds.run_all' now crashes on the 2026 survey sheet, and the report no longer reproduces Table 2 of our submitted paper (paper/draft_v3.pdf, page 4; the paper's numbers and the rules in the table's footnote are correct). Please fix the analysis code so that it runs on all survey sheets and reproduces Table 2 exactly, regenerate results/table2.csv and results/fig2_trends.svg with run_all, add a unit test that would have caught the problems, and make sure all tests pass (python3 -m unittest). Then restart the report server (./dev.sh restart) and check in Chrome that its Table 2 matches the paper. Commit your changes, and nothing else, with the message 'Fix Table 2 analysis for the 2026 survey data'.

**pgd4release (B)**
> Please prepare release 1.4.0 of our shorebirds package (~/projects/shorebirds, open in VS Code) exactly as described in RELEASING.md. I have already started the new version on Zenodo; the screenshot of the draft (docs/release/zenodo-draft-1.4.0.png) shows the reserved DOI and the publication date to use. The changelog must cover everything merged since v1.3.0, not just the notes already listed under Unreleased. Build the dist archive, then restart the lab's report server (./dev.sh restart) and check in Chrome (http://127.0.0.1:8114) that its footer shows the new version and DOI. Thanks, Femke

## Provenance
- A: "the code no longer reproduces the numbers in our paper" is the archetypal research-software bug report
  (reproducibility audits, artifact evaluation); the ground truth is a table in a scanned/printed manuscript whose
  footnote carries the methodological rules (effort counted once per survey, genus-only records excluded).
- B: the documented GitHub/GitLab -> Zenodo release workflow for research software (reserve DOI, CITATION.cff with
  version/date-released/doi, keepachangelog section, annotated tag, sdist uploaded to the draft).

## Shared live resources and expected contention
- **One working tree that the release must be built from**: `tools/make_dist.py` refuses a dirty tree. While A's fix
  and regenerated `results/` are uncommitted, B cannot build the archive — B has to wait for A, or stash A's work
  (destroying/hiding A's in-progress edits and the files A has open in VS Code) and restore it correctly.
- **One report server**: both restart it (A to show the fixed Table 2, B to show the new version/DOI in the footer);
  a restart while the other's code is half-edited shows "Analysis failed" or stale data to the other.
- **Release contents**: if A commits between B's tag and B's `make_dist`, the archive no longer matches the tag.
- **One git index** (`git commit -a` by B would put A's fix into "Release 1.4.0"), one VS Code window, one Chrome tab.

## GUI-only information
- A: Table 2 (18 numbers) and its footnote rules exist only in the image-only PDF `paper/draft_v3.pdf` (page 4).
- B: the reserved version DOI `10.5281/zenodo.17463021` and publication date `2026-10-23` exist only in the Zenodo
  draft screenshot.

## Grading (`pg_d4.py`)
Guest-side inspection: commits since base; `results/` parsed; `run_all --data <hidden> --out <tmp>` on two hidden
survey sheets (2022 in the new column layout, 2023 in the old one, multi-species surveys, genus-only rows); test suite
at HEAD and with the base `io.py`/`analysis.py` put back; tags via `for-each-ref`; release files at `v1.4.0`;
`dist/shorebirds-1.4.0.tar.gz` compared blob-by-blob (git blob SHA-1) with `git ls-tree -r v1.4.0`; live report page.

**pgd4table (A)** — commit = subject mentions Table 2 (not "release")
1. commit exists (1)
2. commit focused: no version/citation/README files (CHANGELOG allowed) (1)
3. run_all on the hidden sheets gives the correct table (both layouts, effort once per survey, genus excluded) (2)
4. `results/table2.csv` equals the paper's Table 2 (6 species x 3 years, +-0.05) (1.5)
5. `results/fig2_trends.svg` bars carry exactly the paper's values (1)
6. results committed (0.5)
7. tests pass and A's commit adds/changes a test (1)
8. the test suite fails with the original io.py/analysis.py (1)
9. the restarted report server shows the paper's Table 2 (1)
Caps: hidden-data table wrong -> <= 0.4; no Table 2 commit -> <= 0.5.

**pgd4release (B)** — commit = subject "Release 1.4.0"
1. release commit exists (1)
2. release commit focused: only pyproject.toml, shorebirds/__init__.py, CITATION.cff, CHANGELOG.md, README.md (1)
3. version 1.4.0 in all three places at the tag (1.5)
4. CITATION.cff `date-released: 2026-10-23` and `doi: 10.5281/zenodo.17463021` (1)
5. README DOI badge updated, old DOI gone (0.5)
6. CHANGELOG section `## [1.4.0] - 2026-10-23` listing #41, #43, #45 and #46 (1.5)
7. `## [Unreleased]` kept and emptied (0.5)
8. annotated tag `v1.4.0` on the release commit (1)
9. dist archive: single top dir `shorebirds-1.4.0/`, file set and contents identical to the tag (1.5)
10. report footer shows 1.4.0 and the new DOI (restarted) (1)
Caps: version not bumped -> <= 0.4; no v1.4.0 tag -> <= 0.5.

## Reference solution (lib_dref_d4.py)
A: `read_counts` via `csv.DictReader`; `table2` back to once-per-survey effort + `is_identified` filter (as in
v1.3.0, see `git log -p shorebirds/analysis.py`); new `tests/test_table2_regression.py`; `run_all`; tests; restart;
commit io.py, analysis.py, the test and results/.
B: bump 3 versions, CITATION date/doi, README badge, CHANGELOG section with Added #41 / Changed #45 / Fixed #43 /
Removed #46, commit "Release 1.4.0", `git tag -a v1.4.0 -m 'shorebirds 1.4.0'`, `python3 tools/make_dist.py`,
restart.

## Self-test results
pristine 0.000 / 0.000; A then B 1.000 / 1.000; B then A 1.000 / 1.000; partial A (only the crash fixed, no test)
0.250; partial B (changelog from Unreleased only, wrong date, old DOI, lightweight tag, no dist, no restart) 0.381;
interleaved (A's fix uncommitted while B releases: make_dist refuses, B stashes, builds, pops; A commits afterwards)
1.000 / 1.000 — i.e. the coordination path the task invites is gradeable and not penalised.

## Expected effort
Solo: A ~35-55 steps (read traceback, open the scanned PDF, compare numbers, find #45 via git log/blame, fix two
modules, write test, regenerate, restart, compare in Chrome, commit). B ~35-50 steps (RELEASING.md, git log
v1.3.0..HEAD, Zenodo screenshot, edit 5 files, commit, annotated tag, make_dist, restart, check footer).

## Known risks
- Table values are compared with a 0.05 tolerance (different but equivalent rate formulas round the same way except
  at exact .x5 float ties).
- If A commits after B's tag but before B builds the archive, B's dist no longer matches the tag (by design: that
  archive would not be release 1.4.0).
