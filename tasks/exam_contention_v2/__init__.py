"""Exam-style GUI+CLI contention suite v2 (broad candidate pool + curated top-5 cases)."""
from __future__ import annotations

from tasks.exam_contention_v2.registry import (
    CANDIDATE_MODULES,
    CANDIDATE_POOL_CATALOG,
    EC2_BY_ID,
    FILTERED_OUT_CANDIDATE_IDS,
    RETAINED_TOP5_CATALOG,
    RETAINED_TOP5_IDS,
)

__all__ = [
    "CANDIDATE_MODULES",
    "CANDIDATE_POOL_CATALOG",
    "EC2_BY_ID",
    "FILTERED_OUT_CANDIDATE_IDS",
    "RETAINED_TOP5_CATALOG",
    "RETAINED_TOP5_IDS",
]
