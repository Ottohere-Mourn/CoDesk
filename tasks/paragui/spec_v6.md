# EXAM-ACCESS1 — accommodation confirmations plus exam seating

Status: compact-fixture scripted positive control and one GPT-6-Sol triplet complete; one-time joint pattern reached. The lock-arm seating failure directly reports shared-work-area switching; accommodations source wording needs cleanup before publication. See EXAM_ACCESS1_MODEL_RESULTS_20261113.md.

## Task pair
- **Accessibility-services coordinator (A):** confirm three approved exam accommodation profiles from authorization notices.
- **Exam coordinator (B):** enter three students' seating, arrival time and equipment assignments exactly as directed by the same notices.
- Both roles work on the same three synthetic student records in the one-window Examination Access Desk; A and B write separate data fields on each record.

## Shared state and common-pass proof
The two output sets are separate fields with a constructed jointly correct state. Seating requirements are present in the source notices and do not depend on whether A has already saved, so B can complete independently and the tasks are not structurally zero-sum. The active student and work-area selector are global. A student's record/panel can change while the other model is part-way through a form, creating a measurable wrong-record or lost-form risk. No private answer or evaluator state is exposed to either actor.

## Oracle and distinction
Both Oracles check exact per-student saved values and read-only DB state. A joint positive-control state passes all six student/panel records; cross-student, wrong-seat and wrong-support controls must fail. This is an education-access workflow with privacy-sensitive consequences, not another video, warehouse, pantry or human-simulator task. Its UI context-switch mechanism is related to the COMMUNITY-PANTRY1/older application-context family, so the contribution is workflow/domain coverage rather than a new mechanism family.

## Controls required before a model run
- offline joint-positive plus wrong-student/wrong-seat negative controls;
- scripted joint-positive Guest GUI run and clean reset;
- both OSWorld-loaded task modules must match source exactly.
No arm-specific timing or force-fail prompt.
