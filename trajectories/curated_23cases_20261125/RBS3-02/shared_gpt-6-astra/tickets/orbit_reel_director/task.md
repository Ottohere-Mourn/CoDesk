# 8-Scene Unobstructed 1920x1080 OrbitMesh Telemetry Reel Work Order — `orbit_reel_director`

## Scope & Deliverables
Capture an unobstructed `1920x1080` fullscreen 8-scene telemetry walkthrough of **OrbitMesh Telemetry** at `http://127.0.0.1:19512/` in the workstation Chromium browser (`127.0.0.1:9222`).

Deliverables:
1. **8 Verified Fullscreen Scene PNGs (`/workspace/frames/scene_1.png` .. `scene_8.png`)**:
   - Place Chromium into unobstructed `1920x1080` fullscreen (`F11` / `>=1840x940` visible tab) and for each scene `1..8`, run its `0.6s` Fullscreen Sweep (`Space` or `Run Fullscreen Sweep`) so `#sigBar` switches from red/amber to the scene's verified color band and displays its `ORB-S*` code, then save a `1920x1080` PNG of the rendered screen.
2. **Animated Walkthrough GIF (`/workspace/orbit_walkthrough.gif`)**:
   - Combine all 8 verified scene frames in order into an animated GIF (`>= 8` frames, `>= 960x540`).
3. **Telemetry Manifest (`/workspace/ORBIT_MANIFEST.json`)** with exact keys:
   - `"scene_codes"` (list of 8 `ORB-S1-...` .. `ORB-S8-...` strings), `"mean_latency_ms"` (float, rounded to 2 decimals), and `"total_flux_gbps"` (float, rounded to 1 decimal).
