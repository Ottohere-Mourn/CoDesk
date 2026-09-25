"""GUI + CLI shared CSV scenario with deterministic stale observation."""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path
from typing import Any

from ..core import Episode, ScriptedOrchestrator


INITIAL = [{"id": "A", "status": "open"}]


class CsvEpisode(Episode):
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="swcub-csv-")
        self.csv_path = Path(self._tmp.name) / "shared.csv"
        self.csv_path.write_text(serialize_csv(INITIAL), encoding="utf-8", newline="")
        super().__init__({"revision": 1})

    def _read_rows(self) -> list[dict[str, str]]:
        with self.csv_path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _write_rows(self, rows: list[dict[str, str]]) -> None:
        self.csv_path.write_text(serialize_csv(rows), encoding="utf-8", newline="")

    @property
    def rows(self) -> list[dict[str, str]]:
        return self._read_rows()

    @property
    def revision(self) -> int:
        return self.state["revision"]

    def snapshot(self) -> Any:
        return {"csv": self.csv_path.read_text(encoding="utf-8"), "rows": self.rows,
                "revision": self.revision}

    def read(self, actor: str) -> tuple[int, list[dict[str, str]]]:
        revision = self.revision
        rows = [dict(row) for row in self.rows]
        self.log.record(actor, "observation", "read:shared.csv", self.snapshot(), self.snapshot(),
                        revision, details={"rows": rows})
        return revision, rows

    def append(self, actor: str, row: dict[str, str]) -> None:
        self.act(actor, "file", f"append:{row['id']}",
                 lambda: (self._write_rows([*self.rows, dict(row)]),
                          self.state.__setitem__("revision", self.revision + 1)),
                 self.revision)

    def set_status(self, actor: str, row_id: str, status: str, observed_revision: int) -> bool:
        stale = observed_revision != self.revision
        def op() -> None:
            rows = self.rows
            row = next(r for r in rows if r["id"] == row_id)
            row["status"] = status
            self._write_rows(rows)
            self.state["revision"] += 1
        self.act(actor, "file", f"update:{row_id}.status={status}", op, observed_revision)
        return stale

    def overwrite_rows(self, actor: str, rows: list[dict[str, str]], observed_revision: int) -> None:
        def op() -> None:
            self._write_rows(rows)
            self.state["revision"] += 1
        self.act(actor, "file", "overwrite:shared.csv", op, observed_revision)


def run_gui_only() -> tuple[CsvEpisode, bool]:
    ep = CsvEpisode()
    rev, _ = ep.read("gui")
    ep.set_status("gui", "A", "done", rev)
    return ep, ep.rows == [{"id": "A", "status": "done"}]


def run_cli_only() -> tuple[CsvEpisode, bool]:
    ep = CsvEpisode()
    ep.read("cli")
    ep.append("cli", {"id": "B", "status": "queued"})
    return ep, ep.rows == [{"id": "A", "status": "open"}, {"id": "B", "status": "queued"}]


def run_paired() -> tuple[CsvEpisode, dict[str, Any]]:
    ep = CsvEpisode()
    obs: dict[str, Any] = {}
    def observe_gui() -> None:
        obs["gui_rev"], obs["gui_rows"] = ep.read("gui")
    def observe_cli() -> None:
        obs["cli_rev"], _ = ep.read("cli")
    def validate() -> None:
        obs["stale"] = obs["gui_rev"] != ep.revision
        ep.log.record("gui", "decision", "validate_revision", ep.snapshot(), ep.snapshot(), obs["gui_rev"],
                      outcome="stale_detected" if obs["stale"] else "fresh",
                      details={"observed_revision": obs["gui_rev"], "current_revision": ep.revision})
    def refresh() -> None:
        obs["fresh_rev"], obs["fresh_rows"] = ep.read("gui")
    ScriptedOrchestrator().run(ep, {
        "gui.read_v1": observe_gui,
        "cli.read_v1": observe_cli,
        "cli.append_b": lambda: ep.append("cli", {"id": "B", "status": "queued"}),
        "gui.check_revision": validate,
        "gui.refresh": refresh,
        "gui.update_a": lambda: ep.set_status("gui", "A", "done", obs["fresh_rev"]),
    }, ["gui.read_v1", "cli.read_v1", "cli.append_b", "gui.check_revision", "gui.refresh", "gui.update_a"])
    gui_rev, cli_rev = obs["gui_rev"], obs["cli_rev"]
    stale, fresh_rows = obs["stale"], obs["fresh_rows"]
    expected = [{"id": "A", "status": "done"}, {"id": "B", "status": "queued"}]
    checks = {
        "gui_goal": next((r["status"] for r in ep.rows if r["id"] == "A"), None) == "done",
        "cli_goal": any(r == {"id": "B", "status": "queued"} for r in ep.rows),
        "no_lost_update": ep.rows == expected,
        "valid_schema": all(set(row) == {"id", "status"} for row in ep.rows),
        "stale_read_detected": stale,
        "refresh_preserved_cli_row": any(r["id"] == "B" for r in fresh_rows),
        "cli_observation_revision": cli_rev,
        "gui_observed_revision": gui_rev,
    }
    return ep, checks


def run_naive_paired() -> tuple[CsvEpisode, dict[str, bool]]:
    ep = CsvEpisode()
    gui_rev, stale_gui_snapshot = ep.read("gui")
    ep.read("cli")
    ep.append("cli", {"id": "B", "status": "queued"})
    # Deliberately write the complete stale snapshot, losing the CLI's appended row.
    stale_gui_snapshot[0]["status"] = "done"
    ep.overwrite_rows("gui", stale_gui_snapshot, gui_rev)
    expected = [{"id": "A", "status": "done"}, {"id": "B", "status": "queued"}]
    checks = {"gui_goal": next((r["status"] for r in ep.rows if r["id"] == "A"), None) == "done",
              "cli_goal": any(r == {"id": "B", "status": "queued"} for r in ep.rows),
              "no_lost_update": ep.rows == expected}
    return ep, checks


def run(out: Path) -> dict[str, Any]:
    gui_ep, gui_ok = run_gui_only()
    cli_ep, cli_ok = run_cli_only()
    ep, checks = run_paired()
    naive_ep, naive_checks = run_naive_paired()
    report = {
        "task_id": "CSV-001", "task_version": "0.1.0",
        "reset_policy": "fresh temporary shared.csv file per episode",
        "independent": {"gui": {"success": gui_ok, "final": gui_ep.snapshot()},
                        "cli": {"success": cli_ok, "final": cli_ep.snapshot()}},
        "joint": {"checks": checks, "success": all(checks[k] for k in
                   ("gui_goal", "cli_goal", "no_lost_update", "valid_schema")),
                  "final": ep.snapshot()},
        "naive_control": {"checks": naive_checks, "success": all(naive_checks.values()),
                          "final": naive_ep.snapshot()},
        "metrics": {"actions_by_actor": ep.action_counts,
                    "total_actions": sum(ep.action_counts.values()),
                    "stale_observations": int(checks["stale_read_detected"]),
                    "recovery_reads": 1},
    }
    ep.write_artifacts(out, report)
    (out / "shared.csv").write_bytes(ep.csv_path.read_bytes())
    return report


def serialize_csv(rows: list[dict[str, str]]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=["id", "status"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
