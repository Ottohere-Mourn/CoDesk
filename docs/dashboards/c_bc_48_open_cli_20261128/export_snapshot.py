#!/usr/bin/env python3
"""Create a sanitized static-dashboard snapshot from completed HealthCare runs.

Only completed runs and their action-linked screenshots are exported. The raw
runner stdout/stderr, prompts, relay bodies, environment files, and evaluator
working directories are deliberately excluded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
REMOTE_BASE = "/mnt/raid1/mjh/codesk-runs/c01-c24-open-cli-20261126"
SECRET_KEYS = {
    "api_key", "apikey", "authorization", "access_token", "refresh_token",
    "auth_token", "token", "secret", "password", "credential", "credentials",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(OPENAI_API_KEY\s*[=:]\s*)[^\s\"']+"),
]

REMOTE_PROGRAM = r'''#!/usr/bin/env python3
import io, json, pathlib, re, sys, tarfile, time
from datetime import datetime, timezone
from pathlib import PurePosixPath

BASE = pathlib.Path("/mnt/raid1/mjh/codesk-runs/c01-c24-open-cli-20261126")
STATE_PATH = BASE / "queue_state.json"
ARCHIVE = pathlib.Path(sys.argv[1])
SECRET_KEYS = {"api_key", "apikey", "authorization", "access_token", "refresh_token", "auth_token", "token", "secret", "password", "credential", "credentials"}
SECRET_PATTERNS = [
 re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
 re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
 re.compile(r"(?i)(OPENAI_API_KEY\s*[=:]\s*)[^\s\"']+"),
]
def clean(v):
 if isinstance(v, dict):
  return {k:("[REDACTED]" if str(k).lower() in SECRET_KEYS or any(x in str(k).lower() for x in ("api_key", "token", "password", "secret", "credential", "authorization")) else clean(x)) for k,x in v.items()}
 if isinstance(v, list): return [clean(x) for x in v]
 if isinstance(v, str):
  for p in SECRET_PATTERNS: v=p.sub("[REDACTED]",v)
  if len(v)>1200 and re.fullmatch(r"[A-Za-z0-9+/=]+",v): return "<BASE64_OMITTED:%dchars>"%len(v)
  return v
 return v
def load_json(p):
 try: return json.loads(p.read_text(encoding="utf-8"))
 except Exception: return {}
def rows_jsonl(p):
 rows=[]
 if p.is_file():
  for line in p.read_text(encoding="utf-8",errors="replace").splitlines():
   if not line.strip(): continue
   try: rows.append(clean(json.loads(line)))
   except Exception: continue
 return rows
def add_bytes(tar,name,data):
 b=json.dumps(data,ensure_ascii=False,separators=(",",":" )).encode("utf-8")
 if re.search(rb"(?i)\bBearer\s+|\bsk-[A-Za-z0-9_-]{16,}\b",b): raise RuntimeError("secret-like value remained after sanitization")
 ti=tarfile.TarInfo(name); ti.size=len(b); ti.mtime=int(time.time()); tar.addfile(ti,io.BytesIO(b))
def screenshot_rel(action):
 a=action.get("screenshot_artifact")
 if not isinstance(a,dict) or not isinstance(a.get("path"),str): return None
 p=PurePosixPath(a["path"].replace("\\","/"))
 if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0]!="shots": return None
 return p
state=load_json(STATE_PATH)
cases=state.get("cases",{})
snapshot={"generated_utc":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
 "queue_updated_utc":state.get("updated_utc"),"mode":state.get("mode"),
 "active_concurrency_cap":state.get("active_concurrency_cap"),"in_flight_guests":state.get("in_flight_guests"),"cases":[]}
manifest={"archive_kind":"sanitized-static-dashboard-snapshot","case_ids":[],"files":[]}
ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(ARCHIVE,"w:gz",compresslevel=5) as tar:
 for cid in sorted(cases,key=lambda x:int(x.rsplit("-",1)[-1])):
  entry=cases[cid] or {}; status=entry.get("status","UNKNOWN")
  item={"id":cid,"status":status,"runId":entry.get("run_id"),
        "steps":entry.get("actions") if isinstance(entry.get("actions"),dict) else {"A":0,"B":0},
        "scores":entry.get("actor_scores") if status=="COMPLETED" else None,
        "traceAvailable":False}
  if status=="COMPLETED":
   run=pathlib.Path(entry.get("run_root", ""))
   try: run.resolve().relative_to((BASE/"runs").resolve())
   except Exception: run=BASE/"runs"/str(entry.get("run_id",""))
   if not run.is_dir():
    item["status"]="COMPLETED_NO_ARCHIVE"
    snapshot["cases"].append(item); continue
   result=load_json(run/"result.json")
   result_agents=result.get("agents") or {}
   scores=entry.get("actor_scores") or {}
   actions={}; relay=[]; declares={"A":False,"B":False}; shot_counts={"A":0,"B":0}
   for actor in ("A","B"):
    role="agent"+actor
    ar=rows_jsonl(run/role/"actions.jsonl")
    actions[actor]=ar
    for action in ar:
     text=json.dumps(action,ensure_ascii=False).lower()
     if "declare_infeasible" in text: declares[actor]=True
     rel=screenshot_rel(action)
     if rel:
      src=run/role/pathlib.Path(*rel.parts)
      if src.is_file():
       dest=f"assets/{cid}/{actor}/"+rel.as_posix()
       tar.add(src,arcname=dest,recursive=False); manifest["files"].append(dest); shot_counts[actor]+=1
      else:
       artifact=action.get("screenshot_artifact")
       if isinstance(artifact,dict): artifact["path"]=None
    add_bytes(tar,f"data/{cid}/actions-{actor}.json",ar)
    rec=result_agents.get(role) or {}
    item.setdefault("actorStatuses",{})[actor]={"status":clean(rec.get("status")),"exit_code":rec.get("exit_code"),"harness":rec.get("harness"),"model":rec.get("model")}
    # Prefer action-log counts; state counts remain a fallback when a runner omitted a file.
    item["steps"][actor]=len(ar) if ar else int(item["steps"].get(actor,0))
   for actor in ("A","B"):
    path=run/f"relay-{actor.lower()}-events.jsonl"
    for row in rows_jsonl(path):
     usage=row.get("usage") if isinstance(row.get("usage"),dict) else {}
     relay.append({"actor":actor,"time":row.get("time"),"elapsed_s":row.get("elapsed_s"),
       "upstream_status":row.get("upstream_status"),"model":row.get("model"),
       "input_image_parts":row.get("input_image_parts"),"input_tokens":usage.get("input_tokens"),
       "output_tokens":usage.get("output_tokens"),"total_tokens":usage.get("total_tokens")})
   relay.sort(key=lambda x: (x.get("time") or 0,x.get("actor") or ""))
   completion=load_json(run/"completion_summary.json")
   end_reason=completion.get("forced_reason") or completion.get("corrected_result_classification") or entry.get("note") or "Runner completed."
   item.update({"scores":scores,"declares":declares,"traceAvailable":True,"relayCount":len(relay),
       "relay200":sum(1 for r in relay if r.get("upstream_status")==200),
       "screenshotCounts":shot_counts,"endReason":clean(end_reason)})
   add_bytes(tar,f"data/{cid}/relay.json",relay)
   add_bytes(tar,f"data/{cid}/summary.json",item)
   manifest["case_ids"].append(cid)
  snapshot["cases"].append(item)
 add_bytes(tar,"snapshot.json",snapshot)
 add_bytes(tar,"manifest.json",manifest)
print(json.dumps({"archive":str(ARCHIVE),"cases":manifest["case_ids"],"files":len(manifest["files"]),"bytes":ARCHIVE.stat().st_size},ensure_ascii=False))
'''


def run_checked(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True, capture_output=capture)


def fetch_snapshot() -> Path:
    nonce = uuid.uuid4().hex[:12]
    remote_script = f"/dev/shm/conc-dashboard-export-{nonce}.py"
    remote_archive = f"/dev/shm/conc-dashboard-export-{nonce}.tar.gz"
    local_archive = Path(tempfile.gettempdir()) / f"conc-dashboard-export-{nonce}.tar.gz"
    script_file = ROOT / f".remote-export-{nonce}.py"
    script_file.write_text(REMOTE_PROGRAM, encoding="utf-8")
    try:
        run_checked(["scp", "-q", str(script_file), f"HealthCare:{remote_script}"])
        result = run_checked(["ssh", "HealthCare", "python3", remote_script, remote_archive], capture=True)
        print(result.stdout.strip())
        run_checked(["scp", "-q", f"HealthCare:{remote_archive}", str(local_archive)])
        return local_archive
    finally:
        script_file.unlink(missing_ok=True)
        subprocess.run(["ssh", "HealthCare", "rm", "-f", "--", remote_script, remote_archive], check=False, capture_output=True)


def safe_extract(archive: Path, destination: Path) -> None:
    allowed_roots = {"data", "assets", "snapshot.json", "manifest.json"}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] not in allowed_roots or member.name.startswith("/") or ".." in parts or not member.isfile():
                raise RuntimeError(f"Unsafe archive member: {member.name}")
        tar.extractall(destination, members=members, filter="data")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_js_data(destination: Path) -> None:
    snapshot = load_json(destination / "snapshot.json")
    cases = []
    for meta in snapshot["cases"]:
        row = dict(meta)
        if row.get("traceAvailable"):
            case_dir = destination / "data" / row["id"]
            row["actions"] = {
                actor: load_json(case_dir / f"actions-{actor}.json")
                for actor in ("A", "B")
            }
            row["relay"] = load_json(case_dir / "relay.json")
        cases.append(row)
    payload = json.dumps({"snapshot": {k:v for k,v in snapshot.items() if k != "cases"}, "cases": cases}, ensure_ascii=False, separators=(",", ":"))
    (destination / "dashboard-data.js").write_text(f"window.CONC_SNAPSHOT={payload};\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="fetch a sanitized snapshot from HealthCare")
    parser.add_argument("--archive", type=Path, help="install an already fetched export archive")
    args = parser.parse_args()
    if not args.fetch and not args.archive:
        parser.error("use --fetch or --archive")
    archive = args.archive or fetch_snapshot()
    destination = ROOT
    (destination / "data").mkdir(exist_ok=True)
    (destination / "assets").mkdir(exist_ok=True)
    safe_extract(archive, destination)
    build_js_data(destination)
    if archive != args.archive:
        archive.unlink(missing_ok=True)
    print(f"Dashboard data written to {destination}; open index.html")


if __name__ == "__main__":
    main()
