"""Public case contract and hidden timeline gold for CDD-TLA-001."""
from __future__ import annotations

from . import CASE_ID, CASE_VERSION, CONDITIONS

FPS = 25
PROJECT_RELATIVE = "project/GreenLoop.kdenlive"
SUBTITLE_RELATIVE = "project/GreenLoop.kdenlive.srt"
SHOT_MANIFEST_RELATIVE = "deliverables/asset_shot_manifest.json"
FINAL_PROJECT_RELATIVE = "deliverables/GreenLoop_Final.kdenlive"
FINAL_SUBTITLE_RELATIVE = "deliverables/GreenLoop_Final.kdenlive.srt"
ASSET_IDS = ("ASSET-01", "ASSET-02", "ASSET-03", "ASSET-04", "AUDIO-01")
PROTECTED_WORKSPACE_FILES = (
    "brief.md", "asset_catalog.json", "project/GreenLoop.kdenlive",
    "project/GreenLoop.kdenlive.srt", "fixture_sha256.json", "assets/clip_01.mp4", "assets/clip_02.mp4",
    "assets/clip_03.mp4", "assets/clip_04.mp4", "assets/music_bed.wav",
)

ACTOR_A_INSTRUCTION = """You are A, the footage curator for the GreenLoop short. Inspect the supplied source clips in the Kdenlive Project Bin/Clip Monitor and use the brief to prepare `deliverables/asset_shot_manifest.json`. Choose the three usable shots that tell the requested intake → wash → reuse story, trim off any visible leader/tail handles, record each asset ID and exact source in/out, explain each choice briefly, and note why the unused outtake should stay out of the cut. Keep the original media and starter project intact. B owns timeline editing in Kdenlive. You may inspect the starter project and all source material; if B finds a shot unsuitable or too short, review the request and revise your manifest as needed. You may message or attach the manifest when useful; no message count or timing is prescribed. Do not edit or save the final timeline project."""

ACTOR_B_INSTRUCTION = """You are B, the video editor for the GreenLoop short. In the supplied Kdenlive starter project, finish the timeline and save `deliverables/GreenLoop_Final.kdenlive` plus its matching subtitle sidecar. Use the shared brief, all source clips, and A's asset shot manifest as useful evidence. Create the requested ordered V1 cut with the specified source ranges, subtitle cues, and music on A1; preserve all source assets in the project bin and do not alter the media. You may inspect footage yourself and may ask A to clarify or revise a selection if it does not fit. You own the final Kdenlive project; do not modify A's shot manifest. Save through Kdenlive GUI in a real episode. Do not infer success from the monitor alone: save, close/reopen in the real-GUI phase, and verify the timeline."""

SINGLE_AGENT_INSTRUCTION = """You are S, responsible for both footage curation and editing the GreenLoop short. Inspect the supplied source clips, write `deliverables/asset_shot_manifest.json` with the selected asset IDs and source ranges, then finish the Kdenlive project and save `deliverables/GreenLoop_Final.kdenlive` with its matching subtitle sidecar. Follow the brief, preserve source files and non-target bin items, and do not use hidden evaluator files. In a real episode, perform project edits through Kdenlive GUI."""

BRIEF = """# GreenLoop — 10-second reuse spot

Finish the partially assembled 320×180, 25 fps GreenLoop project as a 10-second piece showing this progression: receiving sorted packaging, washing it, then putting it back into use. Keep the cut clean and contiguous on **Video 1 (V1)**. Use the supplied footage rather than replacing it with generated imagery. Leave the low-quality outtake unused in the timeline but available in the project bin.

Trim visible leader/tail handles so only each segment's substantive action remains. Add these exact English subtitle lines at their matching story beats, with each cue staying within its shot: “Sort it for a second life.”; “Rinse. Recover. Reuse.”; “Ready for another use.” Keep the supplied instrumental bed on **Audio 1 (A1)** for the complete 10-second cut. Do not alter source media or remove any source clip from the project bin. A will prepare a traceable shot manifest; B owns the final timeline project. Both roles may read all materials and the starter project. The review/feedback channel is available when helpful, but no fixed handoff schedule is required.

The starter project is intentionally partial: it has an opening and closing clip, but it is too short, has the wrong source ranges, lacks the middle wash shot, and has incomplete subtitle/audio coverage. Save the finished project and subtitle sidecar under `deliverables/`."""

# Private scoring reference. It is imported by the evaluator and is not copied
# into an actor's workspace.
GOLD_SHOTS = (
    {"asset_id": "ASSET-01", "source_in_frame": 25, "source_out_frame": 99,
     "timeline_start_frame": 0, "track": "Video 1", "story_role": "intake"},
    {"asset_id": "ASSET-02", "source_in_frame": 25, "source_out_frame": 124,
     "timeline_start_frame": 75, "track": "Video 1", "story_role": "wash"},
    {"asset_id": "ASSET-03", "source_in_frame": 0, "source_out_frame": 74,
     "timeline_start_frame": 175, "track": "Video 1", "story_role": "reuse"},
)
GOLD_SUBTITLES = (
    {"start_ms": 200, "end_ms": 2800, "text": "Sort it for a second life."},
    {"start_ms": 3200, "end_ms": 6800, "text": "Rinse. Recover. Reuse."},
    {"start_ms": 7200, "end_ms": 9800, "text": "Ready for another use."},
)
GOLD_DURATION_FRAMES = 250
GOLD_AUDIO = {"asset_id": "AUDIO-01", "track": "Audio 1", "source_in_frame": 0,
              "source_out_frame": 249, "timeline_start_frame": 0}
GOLD_BIN_ASSETS = set(ASSET_IDS)
GOLD_ASSET_RESOURCES = {
    "ASSET-01": "assets/clip_01.mp4", "ASSET-02": "assets/clip_02.mp4",
    "ASSET-03": "assets/clip_03.mp4", "ASSET-04": "assets/clip_04.mp4",
    "AUDIO-01": "assets/music_bed.wav",
}

PUBLIC_ASSET_CATALOG = {
    "schema_version": 1, "project_profile": {"width": 320, "height": 180, "fps": FPS},
    "assets": [
        {"asset_id": "ASSET-01", "path": "assets/clip_01.mp4", "kind": "video", "duration_frames": 150},
        {"asset_id": "ASSET-02", "path": "assets/clip_02.mp4", "kind": "video", "duration_frames": 175},
        {"asset_id": "ASSET-03", "path": "assets/clip_03.mp4", "kind": "video", "duration_frames": 125},
        {"asset_id": "ASSET-04", "path": "assets/clip_04.mp4", "kind": "video", "duration_frames": 125},
        {"asset_id": "AUDIO-01", "path": "assets/music_bed.wav", "kind": "audio", "duration_frames": 250},
    ],
}
