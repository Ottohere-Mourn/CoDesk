"""WeaveBench-style Shared Full Hybrid GUI+CLI (unlocked, container-unrestricted) arm for CoDesk cases."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import shlex
import threading
import time
import uuid


MODEL = "gpt-6.1-sol"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_action_rows(out: Path, role: str) -> list[dict]:
    log_path = out / "actor_runs" / role / role / "actions.jsonl"
    if not log_path.is_file():
        return []
    rows = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def _summarize_tool_usage(out: Path) -> dict:
    summary = {}
    total_gui = 0
    total_cli = 0
    for role in ("A", "B"):
        by_tool: dict[str, int] = {}
        stdout_log = out / "actor_runs" / role / role / "stdout.log"
        if stdout_log.is_file():
            for line in stdout_log.read_text(encoding="utf-8", errors="replace").splitlines():
                if '"item.completed"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item = ev.get("item") or {}
                itype = item.get("type")
                if itype == "mcp_tool_call":
                    key = f"{item.get('server')}.{item.get('tool')}"
                    by_tool[key] = by_tool.get(key, 0) + 1
                elif itype in {"command_execution", "shell_call"}:
                    by_tool["container.shell"] = by_tool.get("container.shell", 0) + 1
        else:
            for row in _read_action_rows(out, role):
                tname = "desktop." + str(row.get("tool", "unknown"))
                by_tool[tname] = by_tool.get(tname, 0) + 1
        cli_calls = (
            by_tool.get("guest_bash.guest_bash", 0)
            + by_tool.get("guest_cli.run_guest_cli", 0)
            + by_tool.get("container.shell", 0)
            + by_tool.get("desktop.guest_bash", 0)
        )
        gui_calls = sum(
            count for name, count in by_tool.items()
            if name.startswith("desktop.") and name not in {"desktop.screenshot", "desktop.wait", "desktop.declare_infeasible", "desktop.guest_bash"}
        )
        obs_calls = by_tool.get("desktop.screenshot", 0) + by_tool.get("desktop.wait", 0)
        collab_calls = sum(count for name, count in by_tool.items() if name.startswith("collaboration."))
        total_gui += gui_calls
        total_cli += cli_calls
        summary[role] = {
            "total_calls": sum(by_tool.values()),
            "gui_action_calls": gui_calls,
            "cli_calls": cli_calls,
            "observation_calls": obs_calls,
            "collaboration_calls": collab_calls,
            "by_tool": by_tool,
        }
    summary["totals"] = {"gui_action_calls": total_gui, "cli_calls": total_cli}
    return summary


def run_full_cli_shared_case(case_id: str, run_id: str, artifact_parent: Path) -> dict:
    from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
    from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
    from oscombo.guest import Guest
    from oscombo.harness.hybrid_v2 import MCP_PYTHON
    from scripts import run_writer_calc_v1 as base
    from swcub.core import EventLog
    from swcub.resource_safety import ensure_resource_identity

    os.environ["CODESK_FULL_CLI_ARM"] = "1"
    endpoint = (os.environ.get("CODESK_SOL_ENDPOINT") or os.environ.get("SWCUB_SOL_BASE_URL")).rstrip("/")
    out = artifact_parent.expanduser().resolve() / run_id
    out.mkdir(parents=True, exist_ok=False)
    for sub in ("actor_runs", "collaboration", "overlays", "shared", "guest-artifacts/shared", "readiness"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    ledger = out / "resource-events.jsonl"
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
    })
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    ensure_resource_identity(ledger)
    log = EventLog()

    store = ProtocolStore(out / "collaboration", run_id)
    tokens = {role: secrets.token_urlsafe(32) for role in ("A", "B")}
    collab_server = make_server(store, tokens)
    threading.Thread(target=collab_server.serve_forever, daemon=True).start()
    token_envs = {}
    for role in ("A", "B"):
        env_key = f"CODESK_FULLCLI_COLLAB_{role}_{uuid.uuid4().hex[:8].upper()}"
        os.environ[env_key] = tokens[role]
        token_envs[role] = env_key

    ep = None
    desk = None
    relays = []
    started = time.monotonic()
    report = {
        "run_id": run_id,
        "case_id": case_id,
        "condition": "ma_sd_full_cli",
        "runtime_profile": "weavebench-style-shared-full-gui-cli-unlocked",
        "actor_implementation": "ContainerizedCodexHarness (container-unrestricted, guest_bash + desktop + collaboration MCP, no lock)",
        "lock_enabled": False,
        "container_permissions": {
            "mode": "container-unrestricted",
            "scope": "docker-container-only",
            "vm_host_codex_launched": False,
            "sandbox_mode": "workspace-write",
            "approval_policy": "never",
            "shell_tool": True,
            "unified_exec": False,
            "yolo_flag_used": False,
        },
        "model": MODEL,
        "endpoint": endpoint,
        "valid_model_run": False,
        "task_success": False,
    }

    try:
        prompts = {}
        cli_roots = {"A": f"/tmp/codesk_fullcli_{run_id}_A", "B": f"/tmp/codesk_fullcli_{run_id}_B"}
        budget = 20
        token_budget = 16000
        eval_fn = None

        if case_id == "AUTH-1":
            from scripts import local_release_review_app as app
            from scripts import run_auth_identity_hybrid_v2 as mod
            ep, desk, setup = mod._new_guest("shared", out, log, run_id)
            prompts = {"A": mod.PROMPTS["actor_a"], "B": mod.PROMPTS["actor_b"]}
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = app.query_state(desk)
                signoffs = [e for e in st.get("events", []) if e.get("kind") == "signoff"]
                ok = (
                    len(signoffs) == 1
                    and signoffs[0].get("record_id") == "LOT-17"
                    and signoffs[0].get("principal") == "Reviewer-A"
                    and st.get("principal") == "Operator-B"
                )
                return ok, {"final_state": mod._state_summary(st), "signoffs": signoffs}

        elif case_id == "VIEW-1":
            from scripts import local_release_review_app as app
            from scripts import run_viewport_signoff_hybrid_v2 as mod
            ep, desk, setup = mod._new_guest("shared", out, log, run_id)
            prompts = {"A": mod.PROMPTS["actor_a"], "B": mod.PROMPTS["actor_b"]}
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = app.query_state(desk)
                signoffs = [e for e in st.get("events", []) if e.get("kind") == "signoff"]
                scrolled = any((o or {}).get("scroll_y", 0) > 0 for o in st.get("observations", []))
                ok = (
                    len(signoffs) == 1
                    and signoffs[0].get("record_id") == "POL-17"
                    and signoffs[0].get("principal") == "Reviewer-A"
                    and scrolled
                )
                return ok, {"final_state": mod._state_summary(st), "signoffs": signoffs, "scrolled": scrolled}

        elif case_id == "CRM-LU1":
            from scripts import crm_lu1_fixture_v1 as fx
            from scripts import run_crm_lu1_hybrid_v2 as mod
            ep, desk = base.make_desktop("shared", log, out / "guest-artifacts/shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            setup = mod._setup_guest("shared", ep, desk, out, run_id, log)
            cli_roots = {r: f"{setup['cli_root']}_{r}" for r in ("A", "B")}
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod._read_state(desk)
                ok = bool(fx.joint_success(st))
                return ok, {"final_record": st.get("record"), "lost_update_signature": fx.lost_update_signature(st)}

        elif case_id == "SITEACT-STATE1":
            from scripts import run_siteact_state_hybrid_v2 as mod
            from scripts import siteact_state_fixture_v1 as fx
            ep, desk = base.make_desktop("shared", log, out / "guest-artifacts/shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            setup = mod._setup_guest("shared", ep, desk, out, run_id, log)
            cli_roots = {r: f"{setup['cli_root']}_{r}" for r in ("A", "B")}
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod._read_state(desk)
                ok = bool(fx.score_shared_final(st))
                return ok, {"status": st.get("status"), "revision": st.get("revision"), "snapshot": st.get("snapshot")}

        elif case_id == "PAY-1":
            from scripts import pay1_timesheet_fixture_v1 as fx
            from scripts import run_pay1_timesheet_hybrid_v1 as mod
            ep, desk = base.make_desktop("shared", log, out / "shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            cli_roots = {"A": f"/tmp/pay1_cli_{run_id}_A", "B": f"/tmp/pay1_cli_{run_id}_B"}
            ep.cli_action("pay1_dirs", f"mkdir -p {shlex.quote(cli_roots['A'])} {shlex.quote(cli_roots['B'])}")
            try:
                setup = mod._setup(ep, desk, out, run_id, "A", "ma_sd", cli_roots["A"])
            except RuntimeError:
                time.sleep(5.0)
                sm = mod._mcp("screenshot", {}, out, desk, "setup_A_retry", run_id + "-setup-retry", "ma_sd")
                btn = mod._green_center(sm["image"])
                setup = {"role": "clerk", "green_button": btn, "initial_business_state": mod._state(desk)}
            evidence = json.dumps({
                "document_id": fx.CORRECTION_ID,
                "employee_id": fx.EMPLOYEE_ID,
                "week_id": fx.WEEK_ID,
                "corrected_hours_tenths": fx.CORRECTED_HOURS_TENTHS,
                "authorized_by": fx.SUPERVISOR_ID,
                "signed": True,
                "reason_code": fx.CORRECTION_SOURCE["reason_code"],
            }, indent=2)
            mod._write_guest(ep, cli_roots["B"] + "/correction.json", evidence, "pay1_evidence_b")
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod._state(desk)
                ev = fx.evaluate_shared(st)
                _rows, collab = mod._messages(out)
                return bool(ev.get("success") and collab.get("success")), {"oracle": ev, "collaboration": collab}

        elif case_id == "DATA-REL1":
            from scripts import data_rel1_fixture_v1 as fx
            from scripts import run_data_rel1_ma_id_v1 as mod
            ep, desk = base.make_desktop("shared", log, out / "guest-artifacts/shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            cli_roots = {"A": f"/tmp/data_rel1_cli_{run_id}_A", "B": f"/tmp/data_rel1_cli_{run_id}_B"}
            setup = mod.setup_guest("A", ep, desk, out, run_id, cli_roots["A"])
            ep.cli_action("datarel_b", "mkdir -p " + shlex.quote(cli_roots["B"]))
            mod.install_text(ep, cli_roots["B"] + "/PA-SYN-017.json", json.dumps(fx.RESTRICTION_EVIDENCE, indent=2) + "\n", "datarel_b_ev")
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod.api_get(desk)
                ev = fx.evaluate_episode({"A": st, "B": st})
                _rows, collab = mod.collab_events(out)
                return bool(ev.get("success") and collab.get("success")), {"oracle": ev, "collaboration": collab}

        elif case_id == "AP-1":
            from scripts import ap1_remittance_eval_v2 as eval_mod
            from scripts import run_ap1_remittance_hybrid_v2_triplet as mod
            ep, desk = base.make_desktop("shared", log, out / "guest-artifacts/shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            setup = mod._setup_guest(ep, desk, "shared", out, run_id, True)
            cli_roots = {"A": "/tmp/ap1-v021-cli-A", "B": "/tmp/ap1-v021-cli-B"}
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod._read_state(desk)
                b_ev = eval_mod.evaluate_store(st, "credit")
                joint = eval_mod.evaluate_store(st, "shared")
                ok = bool(b_ev.get("success") and joint.get("actor_a", {}).get("success") and joint.get("actor_b", {}).get("success"))
                return ok, {"b_credit": b_ev, "joint": joint}

        elif case_id == "W1":
            from scripts import run_wf_receiving_hybrid_v3 as mod
            from scripts import wf_composite_receiving_v2 as wf
            ep, desk = base.make_desktop("shared", log, out / "shared", require_a11y_tree=False)
            desk.guest_key = "shared"
            setup = mod._setup_guest(ep, desk, "shared", out, run_id)
            cli_roots = {"A": f"/tmp/codesk_cli_{run_id}_a", "B": f"/tmp/codesk_cli_{run_id}_b"}
            prompts = dict(mod.PROMPTS)
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = mod._state(desk)
                ev = wf.evaluate_state(st)
                ev_file = out / "collaboration/events.jsonl"
                c_rows = [json.loads(x) for x in ev_file.read_text().splitlines() if x.strip()] if ev_file.is_file() else []
                collab = wf.collaboration_contract(c_rows)
                return bool(ev.get("condition_success") and collab.get("success")), {"oracle": ev, "collaboration": collab}

        elif case_id == "A-01":
            from scripts import run_a01_hybrid_v2_retest as mod
            from scripts import run_browser_context_v1 as fixture
            ep, desk, setup = mod._new_guest("shared", out, log)
            mod._prepare_tab("A", ep, desk, out, log, "shared", "initial")
            prompts = {"A": mod.PROMPTS["actor_a"], "B": mod.PROMPTS["actor_b"]}
            budget, token_budget = mod.BUDGET, mod.TOKEN_BUDGET

            def eval_fn():
                st = fixture._read_state(desk)
                tabs = st.get("tabs", {})
                ok_a = str(tabs.get("tab-a", {}).get("goal", "")) == fixture.TASK.values["actor_a"]
                ok_b = str(tabs.get("tab-b", {}).get("goal", "")) == fixture.TASK.values["actor_b"]
                return bool(ok_a and ok_b), {"tabs": tabs, "ok_a": ok_a, "ok_b": ok_b}

        elif case_id == "CWD-1":
            from scripts import run_sol_cwd_bundle_v2 as cwd_spec
            from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_tar_exact_files
            ep, desk = base.make_desktop("shared", log, out / "shared", require_a11y_tree=False)
            setup = cwd_spec.setup_terminal(ep, desk, "shared")
            raw_p = cwd_spec.prompts()
            prompts = {"A": raw_p["actor_a"], "B": raw_p["actor_b"]}
            cli_roots = {"A": f"{cwd_spec.ROOT_GUEST}/work/a", "B": f"{cwd_spec.ROOT_GUEST}/work/b"}
            budget, token_budget = 20, 14000

            def eval_fn():
                a_exp = cwd_spec.read_exact(desk, f"{cwd_spec.ROOT_GUEST}/work/a/deliverables/release-note.txt")
                a_wrong = cwd_spec.read_exact(desk, f"{cwd_spec.ROOT_GUEST}/work/b/deliverables/release-note.txt")
                b_chk = cwd_spec.read_exact(desk, f"{cwd_spec.ROOT_GUEST}/work/b/deliverables/check.txt")
                b_tar = cwd_spec.read_exact_bytes(desk, f"{cwd_spec.ROOT_GUEST}/work/b/qa-bundle.tar.gz")
                tar_eval = {"pass": False}
                if b_tar is not None:
                    local_tar = out / "qa-bundle.tar.gz"
                    local_tar.write_bytes(b_tar)
                    tar_eval = evaluate_tar_exact_files(str(local_tar), {"deliverables/check.txt": cwd_spec.B_VALUE.encode("utf-8")})
                ok = (a_exp == cwd_spec.A_VALUE) and (a_wrong is None) and (b_chk == cwd_spec.B_VALUE) and bool(tar_eval.get("pass"))
                return ok, {"a_expected": a_exp == cwd_spec.A_VALUE, "a_wrong_absent": a_wrong is None, "b_check": b_chk == cwd_spec.B_VALUE, "bundle": tar_eval}

        elif case_id in {"C-03", "F-01"}:
            from scripts import run_workflows_qwen_v1 as old
            from scripts import run_workflows_v1 as core
            workflow = core.get_workflow(case_id)
            app_a = workflow.actor_application("actor_a").lower()
            app_b = workflow.actor_application("actor_b").lower()
            ep, desk = base.make_desktop("shared", log, out / "shared", require_a11y_tree=False)
            setup = old._setup_model_desktop(ep, desk, out / "shared", workflow, [app_b, app_a])
            prompts = {"A": old.PROMPTS[case_id]["actor_a"], "B": old.PROMPTS[case_id]["actor_b"]}
            cli_roots = {"A": str(Path(workflow.writer_path).parent), "B": str(Path(workflow.calc_path).parent)}
            budget, token_budget = 20, 14000

            def eval_fn():
                ev = workflow.evaluate(lambda p: base.guest_command(desk, ["cat", p], timeout=25), ("actor_a", "actor_b"))
                return bool(ev.get("success")), ev

        elif case_id in {"S-01", "U-01"}:
            from scripts import run_calc_hybrid_v2_retest as mod
            from scripts import run_calc_mechanism_qwen_v1 as old
            mech = "selection" if case_id == "S-01" else "undo"
            ep, desk, setup = old._setup("shared", log, out)
            raw_p = mod._prompts(mech)
            prompts = {"A": raw_p["actor_a"], "B": raw_p["actor_b"]}
            cli_roots = {"A": "/tmp/swcub_office", "B": "/tmp/swcub_office"}
            budget, token_budget = mod.BUDGET, 14000

            def eval_fn():
                ev = old._evaluate(desk, ["actor_a", "actor_b"], mech)
                return bool(ev.get("success")), ev

        elif case_id in {"EDIT-1", "FIND-1"}:
            from scripts import run_sol_writer_overwrite_v1 as edit
            if case_id == "EDIT-1":
                from scripts import run_edit_overwrite_hybrid_v2_retest as mod
                edit.DOC = (
                    "Release status: STATUS | HOLD-FOR-REVIEW",
                    "Reviewer code: ____; change only this fixed-width code.",
                    "Guard phrase: DO-NOT-ALTER-THIS-LINE",
                )
                expected_lines = [edit.A_TARGET, edit.B_TARGET, edit.GUARD]
            else:
                from scripts import run_find_replace_hybrid_v2 as mod
                edit.DOC = mod.DOC
                expected_lines = [
                    "Status batch: approved / approved / approved",
                    "Archive code: REVIEW",
                    "Protected phrase: PRESERVE EXACTLY.",
                ]
            ep, desk = base.make_desktop("shared", log, out / "shared", require_a11y_tree=False)
            setup = edit.setup_writer(ep, desk, "shared", out / "shared")
            prompts = {"A": mod.PROMPTS["actor_a"], "B": mod.PROMPTS["actor_b"]}
            cli_roots = {"A": "/tmp/swcub_office", "B": "/tmp/swcub_office"}
            budget, token_budget = mod.BUDGET, 14000

            def eval_fn():
                txt = edit.writer_text(desk)
                lines = txt.splitlines()
                return lines == expected_lines, {"actual_lines": lines, "expected_lines": expected_lines}
        else:
            raise ValueError(f"Unsupported case_id for codesk_shared_full_cli: {case_id}")

        for role, croot in cli_roots.items():
            ep.cli_action(f"mk_cli_{role}", f"mkdir -p {shlex.quote(croot)}")
        report["setup"] = setup

        def run_role(role: str) -> dict:
            actor_dir = out / "actor_runs" / role
            actor_dir.mkdir(parents=True, exist_ok=True)
            relay_env = f"CODESK_FULLCLI_RELAY_{role}_{uuid.uuid4().hex[:8].upper()}"
            os.environ[relay_env] = secrets.token_urlsafe(32)
            relay_proc, relay_url = _start_codex_compat_relay(
                actor_dir, endpoint, "SWCUB_SOL_API_KEY", os.environ[relay_env], relay_env,
                output_token_budget=token_budget, response_token_cap=4096, reserve_on_missing_usage=True,
            )
            relays.append(relay_proc)
            guest = Guest(desk)
            guest.guest_key = "shared"
            guest.actor = role
            return _run_model_actor(
                role,
                guest,
                prompts[role],
                out,
                MODEL,
                relay_url,
                "SWCUB_SOL_API_KEY",
                MCP_PYTHON,
                f"http://127.0.0.1:{collab_server.server_port}",
                token_envs[role],
                max_steps=budget,
                effort="medium",
                timeout=2400,
                request_retries=5,
                relay_client_token_env=relay_env,
                hybrid_v2=True,
                condition="collaborative_shared_full_cli",
                episode_id=f"{run_id}-{role}",
                cli_root=cli_roots[role],
                action_lock_file=None,
                mcp_env_overrides=None,
                task_id=f"{case_id}@full_cli",
                desktop_tool_timeout_sec=300,
                full_cli=True,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = {role: pool.submit(run_role, role) for role in ("A", "B")}
            statuses = {role: fut.result() for role, fut in futs.items()}

        time.sleep(2.0)
        task_success, eval_details = eval_fn()
        actors_ok = all(statuses.get(r, {}).get("status") in {"done", "max_steps", "fail"} for r in ("A", "B"))
        tool_usage = _summarize_tool_usage(out)
        report.update({
            "actor_results": statuses,
            "tool_usage": tool_usage,
            "evaluation": eval_details,
            "valid_model_run": bool(actors_ok),
            "task_success": bool(task_success),
            "model_task_outcome": "PASS" if task_success else "FAIL",
            "condition_classification": "Shared_FullCLI_PASS" if task_success else "Shared_FullCLI_FAIL",
            "status": "completed" if actors_ok else "invalid_model_episode",
        })
    except Exception as exc:
        report.update({
            "status": "invalid_setup_or_runtime",
            "valid_model_run": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        })
    finally:
        if ep is not None:
            try:
                ep.close()
            except Exception:
                pass
        for proc in relays:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            collab_server.shutdown()
            collab_server.server_close()
        except Exception:
            pass
        report["wall_seconds"] = round(time.monotonic() - started, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["reset_success"] = bool((report.get("resource_lifecycle") or {}).get("all_containers_have_destroy_record"))
        if not report["reset_success"]:
            report["valid_model_run"] = False
        _write_json(out / "report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    args = parser.parse_args(argv)
    res = run_full_cli_shared_case(args.case, args.run_id, args.artifact_parent)
    print(json.dumps({
        "run_id": res["run_id"],
        "case_id": res["case_id"],
        "status": res.get("status"),
        "valid_model_run": res.get("valid_model_run"),
        "task_success": res.get("task_success"),
        "tool_usage": res.get("tool_usage", {}).get("totals"),
        "wall_seconds": res.get("wall_seconds"),
        "error": res.get("error"),
    }, ensure_ascii=False, indent=2))
    return 0 if res.get("valid_model_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
