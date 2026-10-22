"""File-tree, attachment-integrity and ODT-reference oracle."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from . import spec
from .fixtures import is_real_odt, read_odt, tree_hashes


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream))


def evaluate(workspace: str | Path, initial_workspace: str | Path) -> dict[str, object]:
    root, initial = Path(workspace), Path(initial_workspace)
    checks: dict[str, bool] = {}
    errors: list[str] = []
    try:
        initial_hashes = tree_hashes(initial)
        actual_hashes = tree_hashes(root)
        gold_hashes = tree_hashes(Path(__file__).parent / "fixtures" / "private" / "gold_workspace")
    except (OSError, ValueError) as exc:
        return {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "checks": {"readable_trees": False}, "joint_success": False,
                "errors": [f"workspace tree cannot be read: {exc}"]}

    checks["exact_final_path_set"] = set(actual_hashes) == set(gold_hashes)
    checks["non_target_files_preserved"] = all(
        path in actual_hashes and path in initial_hashes and actual_hashes[path] == initial_hashes[path]
        for path in spec.PROTECTED_PATHS)
    moved_bytes = {}
    for item in spec.ATTACHMENTS:
        source_hash = initial_hashes.get(item["source"])
        target_hash = actual_hashes.get(item["target"])
        moved_bytes[item["asset_id"]] = bool(source_hash and target_hash and source_hash == target_hash)
    checks["all_attachment_bytes_preserved"] = all(moved_bytes.values()) and len(moved_bytes) == len(spec.ATTACHMENTS)
    checks["sources_moved_not_copied"] = all(item["source"] not in actual_hashes for item in spec.ATTACHMENTS)

    manifest_path = root / spec.MANIFEST_FINAL
    try:
        rows = _csv_rows(manifest_path)
        expected_rows = [["asset_id", "relative_path", "sha256", "description"]]
        for item in spec.ATTACHMENTS:
            final_rel = item["target"].removeprefix("delivery/")
            expected_rows.append([item["asset_id"], final_rel, actual_hashes.get(item["target"], ""), item["description"]])
        checks["attachment_manifest_exact"] = rows == expected_rows
    except (OSError, csv.Error, UnicodeError):
        checks["attachment_manifest_exact"] = False

    report_path = root / spec.REPORT_FINAL
    checks["report_is_real_odt"] = is_real_odt(report_path)
    if checks["report_is_real_odt"]:
        try:
            text, links = read_odt(report_path)
            expected_text, _ = read_odt(Path(__file__).parent / "fixtures" / "private" / "gold_workspace" / spec.REPORT_FINAL)
            checks["report_narrative_preserved"] = text == expected_text
            checks["report_links_exact"] = links == spec.REPORT_LINKS
            checks["all_report_links_resolve"] = all(
                (report_path.parent / href).resolve().is_file()
                and (report_path.parent / href).resolve().is_relative_to(root.resolve())
                for href in links.values())
        except (OSError, ValueError, KeyError):
            checks["report_narrative_preserved"] = False
            checks["report_links_exact"] = False
            checks["all_report_links_resolve"] = False
    else:
        checks.update({"report_narrative_preserved": False, "report_links_exact": False,
                       "all_report_links_resolve": False})

    # Attachment paths, filenames and payloads are checked independently from
    # link updates so filesystem operations are not mislabeled as GUI events.
    checks["attachments_match_fixed_gold"] = all(
        actual_hashes.get(path) == gold_hashes.get(path)
        for path in (item["target"] for item in spec.ATTACHMENTS))
    errors = [name for name, passed in checks.items() if not passed]
    actor_a_checks = ("exact_final_path_set", "non_target_files_preserved", "all_attachment_bytes_preserved",
                      "sources_moved_not_copied", "attachment_manifest_exact")
    actor_b_checks = ("report_is_real_odt", "report_narrative_preserved", "report_links_exact",
                      "all_report_links_resolve")
    return {
        "case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
        "actors": {"A": {"success": all(checks.get(key, False) for key in actor_a_checks),
                          "attachment_integrity": moved_bytes},
                   "B": {"success": all(checks.get(key, False) for key in actor_b_checks)}},
        "checks": checks, "joint_success": not errors, "errors": errors,
        "causal_boundary": {
            "filesystem_changes": "measured by path/hash/manifest state; not classified as desktop interference",
            "gui_interference": "requires real action/window/focus trace; not available in offline validation",
        },
        "gold_tree_sha256": hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(gold_hashes.items())).encode()).hexdigest(),
    }
