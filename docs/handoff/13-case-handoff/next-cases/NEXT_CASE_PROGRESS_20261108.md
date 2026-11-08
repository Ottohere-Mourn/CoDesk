# New Candidate Progress - 2026-11-08

## Added case: CRM-LU1

- Card: CRM_LU1_CASE_CARD_V01_20261108.md.
- Outcome: one valid GPT-6-Sol triplet reached the target combination MA-ID PASS / Shared FAIL / Shared+Lock FAIL in a loopback-only synthetic legacy full-record CRM form.
- Exact final failure signature: B's billing email is correct after B's save; A's still-open version-1 full-record form then correctly updates renewal contact but restores the old billing email. Same signature in lock arm. No simultaneous action contention; lock only serializes MCP calls.
- This is a controlled workflow case within the explicitly modeled legacy full-form Save contract, not validation of a current CRM product's default behavior. Keep that caveat attached and do not count this as evidence of general CRM incidence.
- Only one valid screening triplet; no second repetition is required or claimed.
- Earlier CRM-LU1 GUI setup/control attempts with an initial wallpaper screenshot or wrong coordinates remain preserved and are not counted. Current valid scripted GUI control is crm-lu1-gui-semantic-control-20261108-05; it proved normal reload + B reapply recovery and clean teardown.
- Model artifacts and scripts are linked in the case card. No commits/pushes performed, and no prior case evidence was changed.

## Previous candidate roster

Prior case dispositions are unchanged; see NEXT_CASE_PROGRESS_20261107.md. This update does not revise the published/qualified roster or claim a new underlying mechanism outside the narrow stale full-record lost-update signature.

