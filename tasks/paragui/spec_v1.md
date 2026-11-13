# VIDEO-REVIEW1 ? loading-bay safety and maintenance clip review

Status: one valid GPT-6-Sol triplet completed; first-pass tuple reached, pending portfolio review.

## Requests
- **Safety reviewer:** inspect NL-448 / camera B and record four distinct pedestrian/egress hazards in the Safety follow-up worklist.
- **Maintenance coordinator:** inspect the same clip and record five equipment defects in Maintenance.
- The prompts describe normal independent duties. Neither mentions the other actor.

## Shared state and realistic contention
Both users work at one workstation in a legacy clip-review desk whose currently selected frame/playhead is shared by the browser session. A saved observation takes its timestamp from the visible global playhead. To record an observation, a reviewer must inspect a frame, select the correct worklist, type a note, then submit. Another reviewer moving the shared playhead between inspection and submission can attach the note to the wrong moment. The per-action lock serializes each GUI call but not the multi-action inspect?note?submit workflow. This is a media-review workflow state (temporal cursor), not viewport scrolling or a shared document undo stack.

## Joint feasibility
The worklists are independent and append-only. A and B have disjoint target frames; the common PASS end state is all four Safety markers and all five Maintenance markers at their correct clip times. There is no capacity limit, deletion, or mutually exclusive status. Sequential completion in either order should preserve all markers. MA-ID tasks start with identical clip content and private database copies.

## Clip contents
The app presents a 13-frame, timecoded clip storyboard as review stills. Safety targets: frames 2, 4, 6, 8. Maintenance targets: frames 3, 5, 7, 9, 11. Other frames are neutral controls. Frame observations are visible only in the Clip Review Desk; hidden fixture/oracle data remain host-side.

## Oracle and evidence boundaries
Each evaluator scores its own worklist by target frame/time and a nontrivial note. Extra unrelated markers are not required and do not invalidate the other actor. Only a wrong/missing timestamp tied to a different actor's playhead movement can support the mechanism hypothesis; omissions, category errors, reset/evaluator issues or ordinary misclassification are not interference evidence. Scripted controls can show the playhead mechanism but cannot substitute for natural model runs.

## Novelty / risk
The nearest old mechanism is VIEW-1, but the shared state differs: a media review playhead whose value is captured at submission, not a viewport coordinate/scroll position. The work domain is simultaneous safety and maintenance evidence review. An exact Guest pilot must confirm GUI usability and that the shared page is one active session. A controlled natural interleaving may verify marker timestamp capture; model agents may re-seek or recover, which must be scored honestly.
