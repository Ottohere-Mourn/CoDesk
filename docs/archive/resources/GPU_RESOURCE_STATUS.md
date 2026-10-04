# 4090 GPU resource status

Read-only snapshot: host supermicr-EG840G-G20, 2026-10-02 11:16 +08:00. Queried nvidia-smi, /proc, ps, CPU pressure, meminfo and a short vmstat sample. No process was changed and no other user's working directory was accessed. Secret-like command-line arguments were redacted.

All eight cards are NVIDIA GeForce RTX 4090, 49,140 MiB each. Utilization was 0% at the instant, but every card had compute processes. Per-process memory is MiB.

| GPU | Used / free MiB | Util | Owner; active PIDs, task/model and VRAM |
|---:|---:|---:|---|
| 0 | 29,452 / 19,059 | 0% | fzx (4): 2971439 Pick_Blocks_Distance_5 / glm-5.3-flash 6,422; 2971134 Pick_Blocks_Canonical_5 / glm-5.3-flash 8,914; 2974965 Stamp_Seals_Order_3 / gpt-6-astra 6,046; 2975808 Pick_Cans_Relational_1 / glm-5.3-flash 7,474 |
| 1 | 48,509 / 2 | 0% | fzx (6): 2973099 Pick_Blocks_Length_3 / glm-5.3-flash 6,417; 2975191 Stamp_Seals_Press_Stapler_3 / gpt-6-astra 12,656; 2975886 Pick_Cans_Relational_3 / glm-5.3-flash 8,657; 2975044 Stamp_Seals_Order_5 / gpt-6-astra 7,385; 3693402 Pick_Mixed_Objects_Distance_B_5 / glm-5.3-flash 6,523; 3849003 Pick_Mixed_Objects_Multi_View_A_1 / glm-5.3-flash 6,751 |
| 2 | 28,197 / 20,314 | 0% | fzx (4): 2972935 Pick_Blocks_Length_1 / glm-5.3-flash 7,655; 2973201 Pick_Blocks_Length_5 / glm-5.3-flash 6,415; 2978018 Pick_Cups_Canonical_3 / glm-5.3-flash 6,841; 2997088 Pick_Mixed_Objects_Distance_B_1 / glm-5.3-flash 7,199 |
| 3 | 40,567 / 7,944 | 0% | fzx (5): 2972508 Pick_Blocks_Height_5 / glm-5.3-flash 7,655; 2974658 Stack_Blocks_Size_Order_5 / gpt-6-astra 11,387; 2978209 Pick_Mixed_Objects_Canonical_A_1 / glm-5.3-flash 7,239; 2996936 Pick_Mixed_Objects_Distance_A_3 / glm-5.3-flash 6,927; 2997011 Pick_Mixed_Objects_Distance_A_5 / glm-5.3-flash 7,259 |
| 4 | 39,836 / 8,675 | 0% | fzx (5): 2971440 Pick_Blocks_Height_1 / glm-5.3-flash 6,435; 2972308 Pick_Blocks_Height_3 / glm-5.3-flash 7,655; 2974891 Stamp_Seals_Order_1 / gpt-6-astra 7,799; 2978117 Pick_Cups_Canonical_5 / glm-5.3-flash 6,649; 2978412 Pick_Mixed_Objects_Canonical_A_5 / glm-5.3-flash 11,193 |
| 5 | 27,518 / 20,993 | 0% | fzx (3): 2971133 Pick_Blocks_Distance_3 / glm-5.3-flash 10,129; 2978284 Pick_Mixed_Objects_Canonical_A_3 / glm-5.3-flash 7,599; 2978490 Pick_Mixed_Objects_Canonical_B_1 / glm-5.3-flash 9,717 |
| 6 | 35,238 / 13,273 | 0% | fzx (4): 2974734 Pick_Blocks_Size_1 / glm-5.3-flash 7,655; 2974574 Stack_Blocks_Size_Order_3 / gpt-6-astra 12,621; 2976186 Pick_Cans_Relational_5 / glm-5.3-flash 7,467; 2979787 Pick_Mixed_Objects_Canonical_B_3 / glm-5.3-flash 7,409 |
| 7 | 29,852 / 18,659 | 0% | fzx (3): 2975265 Stamp_Seals_Press_Stapler_5 / gpt-6-astra 9,077; 2977700 Pick_Cups_Canonical_1 / glm-5.3-flash 11,345; 2979863 Pick_Mixed_Objects_Canonical_B_5 / glm-5.3-flash 9,355 |

The 34 GPU compute PIDs were all owned by fzx. Their process was RoboDawn harness/run_robotwin_eval.py for RoboTwin tasks using GLM-5.3-flash or gpt-6-astra. This identifies current ownership/job family, not expected finish time.

## Host pressure and decision

| Metric | Snapshot |
|---|---|
| Logical CPUs | 80 |
| Load average, 1/5/15 min | 6.45 / 3.09 / 2.10 |
| CPU PSI | some avg10/60/300 = 0%; full = 0% |
| RAM available | 44,201,276 KiB (~42.2 GiB) of 263,741,356 KiB |
| Swap | 2 GiB total, 152 KiB free (effectively full) |
| Short vmstat | about 99% idle CPU; swap-in/out 0 in sample |

CPU is not the current blocker. RAM headroom is finite and swap is nearly full, a secondary caution. GPU allocation is the direct blocker: 0% utilization is not free capacity when every card has compute PIDs and resident allocations.

Qwen3-VL-30B-A3B BF16 requires roughly 60+ GB of weights before runtime overhead; two empty 4090s may be a candidate if the fixed baseline fits. No pair is safe in this snapshot: every card has compute PIDs, GPU 1 has only 2 MiB free, and all other cards also host fzx work. Do not launch Qwen or use the claim tool against this snapshot.

Recommended contact: fzx or the person coordinating that account's RoboTwin jobs. Ask whether a two-GPU allocation can be explicitly released/assigned; do not signal jobs directly.
