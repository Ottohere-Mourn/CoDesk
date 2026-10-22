from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import spec
from .fixtures import build_fixture
from .oracle import evaluate, read_odp, read_ods
from .plan import make_plan, validate_live_prerequisites
from .protocol import ProtocolStore, make_server


def _parser():
    p = argparse.ArgumentParser(prog="python -m oscombo.collab.data_to_deck")
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="create deterministic source fixtures")
    prep.add_argument("output", type=Path)
    plan = sub.add_parser("plan", help="print condition topology and budgets")
    plan.add_argument("condition", choices=spec.CONDITIONS)
    plan.add_argument("--check-live", action="store_true")
    score = sub.add_parser("evaluate", help="evaluate role outputs using the hidden oracle")
    for arg in ("authority", "analysis", "draft", "deck"):
        score.add_argument(f"--{arg}", type=Path, required=True)
    score.add_argument("--output", type=Path)
    proto = sub.add_parser("protocol-smoke", help="offline message/attachment roundtrip")
    proto.add_argument("--output", type=Path)
    serve = sub.add_parser("serve", help="run the loopback-only case message/attachment API")
    serve.add_argument("--root", type=Path, required=True)
    serve.add_argument("--run-id", required=True)
    serve.add_argument("--condition", choices=spec.CONDITIONS, default="collaborative_shared")
    serve.add_argument("--port", type=int, default=0)
    office = sub.add_parser("local-office-smoke", help="headless host LibreOffice import/export smoke; not Guest evidence")
    office.add_argument("--workdir", type=Path)
    return p


def _protocol_smoke(root: Path) -> dict[str, object]:
    store = ProtocolStore(root, "offline-protocol-smoke")
    attachment = store.put_attachment("A", "analysis-note.txt", b"Q2 to Q3 revenue delta = 30")
    message = store.send("A", "B", "Verified bridge attached.", [str(attachment["attachment_id"])])
    received = store.messages("B")
    payload = store.get_attachment("B", str(attachment["attachment_id"]))
    return {"message_visible_to_recipient": len(received) == 1 and received[0]["message_id"] == message["message_id"],
            "attachment_roundtrip": payload == b"Q2 to Q3 revenue delta = 30",
            "event_log": str(store.log_path), "attachment_sha256": attachment["sha256"]}


def _local_office_smoke(workdir: Path | None) -> dict[str, object]:
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    if not binary:
        return {"status": "BLOCKED", "reason": "LibreOffice binary not found"}
    owned_tmp = tempfile.TemporaryDirectory(prefix="codesk-data-to-deck-") if workdir is None else None
    root = Path(owned_tmp.name if owned_tmp else workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    src, out, profile = root / "source", root / "roundtrip", root / "profile"
    src.mkdir(exist_ok=True); out.mkdir(exist_ok=True); profile.mkdir(exist_ok=True)
    build_fixture(src)
    profile_uri = profile.as_uri()
    results = []
    converted_paths = []
    for filename, target in ((spec.FIXTURE_NAMES["authority"], "xlsx"),
                             (spec.FIXTURE_NAMES["draft"], "pptx")):
        cmd = [binary, "--headless", "--nologo", "--nodefault", "--nofirststartwizard",
               f"-env:UserInstallation={profile_uri}", "--convert-to", target, "--outdir", str(out),
               str(src / filename)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
            converted = out / (Path(filename).stem + f".{target}")
            results.append({"source": filename, "returncode": proc.returncode,
                            "output_exists": converted.is_file(), "stdout": proc.stdout[-2000:],
                            "stderr": proc.stderr[-2000:]})
            if converted.is_file():
                converted_paths.append(converted)
        except subprocess.TimeoutExpired as exc:
            results.append({"source": filename, "timeout": True, "stdout": str(exc.stdout)[-1000:],
                            "stderr": str(exc.stderr)[-1000:]})
    # Save back to ODF, then reopen by exporting to PDF.  This checks host LO
    # import/save/reopen behavior without claiming OSWorld Guest compatibility.
    roundtrip_paths = []
    for path, target in zip(converted_paths, ("ods", "odp")):
        cmd = [binary, "--headless", "--nologo", "--nodefault", "--nofirststartwizard",
               f"-env:UserInstallation={profile_uri}", "--convert-to", target, "--outdir", str(out), str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
            roundtrip = out / (path.stem + f".{target}")
            results.append({"source": path.name, "save_as": target, "returncode": proc.returncode,
                            "output_exists": roundtrip.is_file(), "stdout": proc.stdout[-2000:],
                            "stderr": proc.stderr[-2000:]})
            if roundtrip.is_file():
                roundtrip_paths.append(roundtrip)
        except subprocess.TimeoutExpired:
            results.append({"source": path.name, "save_as": target, "timeout": True})
    reopened = []
    reserialized_content = []
    for path in roundtrip_paths:
        try:
            if path.suffix == ".ods":
                sheets = read_ods(path)
                valid = (len(sheets.get("Sales", [])) == 13 and len(sheets.get("Costs", [])) == 13
                         and len(sheets.get("Quarterly_Summary", [])) == 5
                         and len(sheets.get("Reconciliation", [])) == 1)
                reserialized_content.append({"source": path.name, "valid": valid,
                                             "sheet_names": sorted(sheets)})
            else:
                pages = read_odp(path)
                reserialized_content.append({"source": path.name, "valid": len(pages) == 3,
                                             "page_count": len(pages)})
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            reserialized_content.append({"source": path.name, "valid": False, "error": str(exc)})
        cmd = [binary, "--headless", "--nologo", "--nodefault", "--nofirststartwizard",
               f"-env:UserInstallation={profile_uri}", "--convert-to", "pdf", "--outdir", str(out), str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
            pdf = out / (path.stem + ".pdf")
            reopened.append({"source": path.name, "returncode": proc.returncode, "pdf_exists": pdf.is_file(),
                             "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]})
        except subprocess.TimeoutExpired:
            reopened.append({"source": path.name, "timeout": True})
    results.extend({"reopen_check": x} for x in reopened)
    results.extend({"reserialized_content_check": x} for x in reserialized_content)
    ok = (len(results) == 8 and all(x.get("returncode") == 0 and x.get("output_exists") for x in results[:4])
          and all(x.get("reopen_check", {}).get("returncode") == 0
                  and x.get("reopen_check", {}).get("pdf_exists") for x in results[4:6])
          and all(x.get("reserialized_content_check", {}).get("valid") for x in results[6:]))
    response = {"status": "PASS" if ok else "FAIL", "scope": "host-local LO import/export only; not Guest compatibility",
                "version": subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10).stdout.strip(),
                "results": results, "workdir": str(root)}
    if owned_tmp:
        response["temporary_workdir"] = "automatically removed after command exits"
        owned_tmp.cleanup()
    return response


def main():
    args = _parser().parse_args()
    if args.command == "prepare":
        print(json.dumps(build_fixture(args.output), indent=2, sort_keys=True))
    elif args.command == "plan":
        plan = make_plan(args.condition)
        result = {**plan.__dict__}
        if args.check_live:
            result["live_blockers"] = validate_live_prerequisites()
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "evaluate":
        result = evaluate(args.authority, args.analysis, args.draft, args.deck)
        raw = json.dumps(result, indent=2, sort_keys=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(raw + "\n", encoding="utf-8")
        print(raw)
        raise SystemExit(0 if result["joint_success"] else 2)
    elif args.command == "protocol-smoke":
        if args.output:
            result = _protocol_smoke(args.output)
        else:
            with tempfile.TemporaryDirectory(prefix="codesk-protocol-smoke-") as temporary:
                result = _protocol_smoke(Path(temporary))
                result["temporary_run_root"] = "automatically removed after command exits"
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(0 if result["message_visible_to_recipient"] and result["attachment_roundtrip"] else 2)
    elif args.command == "serve":
        actors = make_plan(args.condition).roles
        tokens = {actor: os.environ.get(f"CODESK_CDD_TOKEN_{actor}") or secrets.token_urlsafe(32) for actor in actors}
        server = make_server(ProtocolStore(args.root, args.run_id), tokens, port=args.port)
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "tokens": tokens,
                          "run_id": args.run_id, "bind": "loopback only"}, sort_keys=True), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    elif args.command == "local-office-smoke":
        result = _local_office_smoke(args.workdir)
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
