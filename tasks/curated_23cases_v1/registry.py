"""Unified catalog and module map for all 23 selected high-quality benchmark cases."""
from __future__ import annotations

from typing import Any

from tasks.authentic_workstation_v1.registry import AW_BY_ID, AW_MODULES, RETAINED_TOP5_IDS as AW_IDS
from tasks.curated_8cases_v1.registry import CURATED_8_BY_ID, CURATED_8_IDS, CURATED_8_MODULES
from tasks.novel_frontier_v1.registry import CANDIDATE_MODULES as NF1_MODULES, NF_BY_ID as NF1_BY_ID, RETAINED_TOP5_IDS as NF1_IDS
from tasks.novel_frontier_v2.registry import CANDIDATE_MODULES as NF2_MODULES, NF2_BY_ID, RETAINED_TOP5_IDS as NF2_IDS

SELECTED_23_IDS: tuple[str, ...] = CURATED_8_IDS + AW_IDS + NF1_IDS + NF2_IDS

SELECTED_23_MODULES: dict[str, Any] = {
    **CURATED_8_MODULES,
    **{tid: AW_MODULES[tid] for tid in AW_IDS},
    **{tid: NF1_MODULES[tid] for tid in NF1_IDS},
    **{tid: NF2_MODULES[tid] for tid in NF2_IDS},
}

SELECTED_23_BY_ID: dict[str, dict[str, Any]] = {
    **CURATED_8_BY_ID,
    **{tid: AW_BY_ID[tid] for tid in AW_IDS},
    **{tid: NF1_BY_ID[tid] for tid in NF1_IDS},
    **{tid: NF2_BY_ID[tid] for tid in NF2_IDS},
}

SELECTED_23_CATALOG: list[dict[str, Any]] = [SELECTED_23_BY_ID[tid] for tid in SELECTED_23_IDS]
