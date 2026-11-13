# CoDesk case handoff package

Start with HANDOFF.md for the current 19-case roster and qualification count. The latest audit is QUALIFIED_CASE_AUDIT_20261108.md: 14 cases have one valid Isolated PASS / Shared FAIL / Shared+Lock FAIL screening triplet; five do not currently meet that target. This is one screening triplet per qualified case, not a repeatability or incidence estimate.

- next-cases/: AP-1, SITEACT-STATE1, and CRM-LU1 case cards; CRM-LU1 progress note.
- QUALIFIED_CASE_AUDIT_20261108.md: superseding current count, inclusion rule, latest 14-case list, causal scope, and exclusions.
- QUALIFIED_CASE_AUDIT_20261107.md: preserved historical audit snapshot (11/16 before AP-1, SITEACT-STATE1, and CRM-LU1 were added).
- next-five/NEXT_CASE_PROGRESS_20261107.md: earlier candidate-batch review.
- next-five/design/NEXT_CASE_IDEAS_20261107.md: concept-only candidates; none are qualified.
- Adjacent folders contain case234 copies, earlier case specs/reports, and compact evidence manifests.

The new case scripts are the exact HealthCare screening versions and retain environment-specific absolute paths. They are reviewable from this branch but are not portable rerun commands without the HealthCare CoDesk Hybrid/OSWorld Guest dependencies and path configuration. Raw screenshots, event traces, and model reports remain on HealthCare RAID1; this branch includes run IDs and summaries, not large raw artifacts. Never add API credentials to Git.
