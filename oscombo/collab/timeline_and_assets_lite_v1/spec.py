"""Public contract for the native Kdenlive Case 4 Lite repair."""

CASE_ID = "CDD-TLA-LITE-001"
CASE_VERSION = "1.0.0"
PAIR_MAX_STEPS = 15
FPS = 25
GUEST_ROOT = "/home/user/codesk-case4-smoke"
PROJECT = "project/GreenLoop.kdenlive"
CONDITIONS = ("collaborative_isolated", "collaborative_shared")
MEDIA = ("clip_01.mp4", "clip_02.mp4", "clip_03.mp4", "clip_04.mp4", "music_bed.wav")

ACTOR_A_INSTRUCTION = """You are A, the footage reviewer and asset-manifest owner. Kdenlive is open with GreenLoop; shot_manifest.txt is already open in a minimized Visual Studio Code window, restorable via the blue VS Code dock icon. Use Kdenlive's Project Bin and Clip Monitor to inspect clip_02.mp4 and clip_04.mp4. The middle beat needs a real WASH action rather than a static leader/outtake; a 4-second candidate is staged on V2 beyond the intended 10-second cut. As soon as you identify the correct source, send B a collaboration message naming the correct filename, wrong filename, and 3–7 second slot. Then, while B edits the timeline, restore the GUI editor and change only the first line of shot_manifest.txt from middle_source=UNCONFIRMED to middle_source=clip_02.mp4; preserve the other two lines and save the file. Do not wait for B before saving your manifest. Do not edit the timeline. Use only the GUI and collaboration tools; do not use Terminal, scripts, or direct filesystem APIs."""

ACTOR_B_INSTRUCTION = """You are B, the Kdenlive editor. The intended GreenLoop cut is 10 seconds at 25 fps. Inspect V1 now: its middle 3–7 second slot uses an outtake. A correctly trimmed 4-second candidate clip is staged on V2 at 11–15 seconds, outside the intended cut. You may select the wrong V1 clip while A reviews footage, but wait for A's collaboration message before deleting it. As soon as A confirms the source, begin the Kdenlive repair while A separately updates the asset manifest in the GUI editor. Delete only the V1 outtake, move the staged V2 clip to V1 at exactly 3–7 seconds, and save GreenLoop.kdenlive. Preserve 0–3 second INTAKE, 7–10 second REUSE, the full 0–10 second A1 music bed, and all five Project Bin assets. Final V2 must be empty. Tell A what you actually saved. Use only Kdenlive GUI and collaboration tools; do not use Terminal, scripts, or XML editing. Do not stop after a plan or message: save the edited project."""

SINGLE_AGENT_INSTRUCTION = """Repair GreenLoop's intended 10-second Kdenlive timeline. Inspect clips in the Project Bin and Clip Monitor; replace the static leader/outtake at V1 3–7 seconds with the staged 4-second WASH action clip currently on V2 at 11–15 seconds. Preserve V1 0–3 INTAKE, V1 7–10 REUSE, A1 0–10 music, all bin assets, and leave V2 empty. Save GreenLoop.kdenlive. Use only the GUI; no Terminal, scripts, or XML editing."""

PUBLIC_BRIEF = """# GreenLoop timeline repair (Case 4 Lite)

The native Kdenlive project has an intended 10-second, 320×180, 25 fps cut with an audio bed. The middle 3–7 second V1 shot mistakenly shows a static leader/outtake. A 4-second WASH candidate is staged on V2 at 11–15 seconds, outside the intended cut. Inspect the synthetic clips, then delete the wrong V1 shot and move the correct staged shot into the middle slot. Preserve INTAKE and REUSE, the 10-second music bed, all five bin assets, and leave V2 empty. Save the existing project. A reviews footage, communicates the selection, and updates shot_manifest.txt in the GUI editor while B performs the Kdenlive timeline edit. The project and media are fixed across isolated and shared desktop conditions.
"""
