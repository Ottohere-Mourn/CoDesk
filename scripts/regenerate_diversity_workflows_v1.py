#!/usr/bin/env python3
"""Regenerate only the approved low-diversity workflows in CoDesk V1 final.

The script preserves the old target instances in a versioned snapshot, keeps all
non-target manifest rows/assets unchanged, and never starts a Guest or model.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from swcub.production_v1 import (
    DOMAINS,LAYOUTS,_PROFILE_ROWS,build_instance,materialize,read_manifest,
    audit_records,evaluate_oracle,_positive_state,_negative_state,canonical_bytes,
    sha256,workflow_registry,git_commit,
)
from swcub.runtime_v1 import compile_suite
from swcub.runtime_bindings_v1 import build_runtime_binding_registry

TARGETS={"A-02","A-03","C-01","C-06","F-01","F-06","S-01","S-02","S-04","U-03","U-N1"}
SUITE=ROOT/"benchmarks/codesk_v1_final"
SNAPSHOT=ROOT/"benchmarks/codesk_v1_final_history/pre_diversity_refresh_20261008"

def digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_raw_manifest(path:Path):
    raw={}
    for line in path.read_text().splitlines():
        if not line.strip():continue
        row=json.loads(line);raw[row["instance_id"]]=(line,row)
    return raw

def copy_record_assets(row,source_root,dest_root):
    inst=row["instance_id"]
    shutil.copytree(source_root/"instances"/inst,dest_root/"instances"/inst)
    evaluator=row["evaluator_path"]
    (dest_root/evaluator).parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source_root/evaluator,dest_root/evaluator)
    for asset in row["fixture_files"]:
        src=source_root/asset["path"];dst=dest_root/asset["path"]
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    if not SUITE.is_dir():raise SystemExit(f"missing final suite: {SUITE}")
    if SNAPSHOT.exists():raise SystemExit(f"refusing to overwrite history snapshot: {SNAPSHOT}")
    old_raw=load_raw_manifest(SUITE/"manifest.jsonl")
    old_rows=[r for _,r in old_raw.values()]
    if len(old_rows)!=600:raise SystemExit(f"expected 600 rows, got {len(old_rows)}")
    if {r["workflow_id"] for r in old_rows}!={x["workflow_id"] for x in workflow_registry()}:
        raise SystemExit("workflow set drift; refusing partial regeneration")
    if any(sum(r["workflow_id"]==w for r in old_rows)!=20 for w in {r["workflow_id"] for r in old_rows}):
        raise SystemExit("non-20 quota found")
    before={w:[r for r in old_rows if r["workflow_id"]==w] for w in TARGETS}
    base_hash=digest(SUITE/"manifest.jsonl")
    workflow_before={w:json.loads((SUITE/"workflows"/f"{w}.json").read_text()) for w in TARGETS}
    registry={r["workflow_id"]:r for r in workflow_registry()}
    for w in TARGETS:
        if workflow_before[w]["operation_graph"]!=registry[w]["operation_graph"]:
            raise SystemExit(f"{w}: operation graph changed")
        if workflow_before[w]["schedule_policy_id"]!=registry[w]["schedule_policy_id"]:
            raise SystemExit(f"{w}: schedule policy changed")

    with tempfile.TemporaryDirectory(prefix="codesk-diversity-v1-") as td:
        stage=Path(td)
        for name in ("instances","fixtures","evaluators"): (stage/name).mkdir()
        new_rows=[]
        layout=next(x for x in LAYOUTS if x["id"]=="guard_after")
        for wid in sorted(TARGETS):
            if len(_PROFILE_ROWS[wid])!=5:raise SystemExit(f"{wid}: expected five profiles")
            for domain in DOMAINS:
                for profile in _PROFILE_ROWS[wid]:
                    spec=build_instance(wid,domain,profile,layout,2026,ROOT)
                    spec.provenance["source_commit"]=git_commit(ROOT)
                    row=materialize(spec,stage)
                    ev=json.loads((stage/row["evaluator_path"]).read_text())
                    pos=evaluate_oracle({"workflow_id":wid,"evaluator":ev},_positive_state(spec))
                    neg=evaluate_oracle({"workflow_id":wid,"evaluator":ev},_negative_state(spec))
                    if not pos["joint_success"] or neg["joint_success"]:
                        raise SystemExit(f"{wid}/{row['instance_id']}: oracle gate failed")
                    for asset in row["fixture_files"]:
                        if sha256((stage/asset["path"]).read_bytes())!=asset["sha256"]:
                            raise SystemExit(f"fixture hash mismatch: {asset['path']}")
                    new_rows.append(row)
        if len(new_rows)!=220 or len({r["instance_id"] for r in new_rows})!=220:
            raise SystemExit("candidate quota/identity gate failed")
        candidate_audit=audit_records(new_rows)
        if candidate_audit["duplicate_rejected"]:raise SystemExit(f"candidate duplicates: {candidate_audit}")
        # Runtime compilation is checked against the full staged candidate asset set.
        partial_manifest=stage/"manifest.jsonl"
        partial_manifest.write_text("".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n" for r in sorted(new_rows,key=lambda r:(r["workflow_id"],r["instance_id"]))))
        compile_result=compile_suite(partial_manifest,stage,stage/"runtime_plans.jsonl")
        if compile_result.get("failed") or compile_result.get("compiled")!=220:
            raise SystemExit(f"candidate runtime compile failed: {compile_result}")
        bindings=build_runtime_binding_registry()
        for line in (stage/"runtime_plans.jsonl").read_text().splitlines():
            plan=json.loads(line);wid=plan["workflow_id"];binding=plan["runtime_execution_binding"]
            if binding.get("missing_components"):raise SystemExit(f"{wid}: missing runtime components")
            if not all(callable(bindings[wid].get(k)) for k in ("setup","initial_verifier","evaluator","event_gate")):
                raise SystemExit(f"{wid}: incomplete runtime binding")

        retained=[r for r in old_rows if r["workflow_id"] not in TARGETS]
        merged=sorted(retained+new_rows,key=lambda r:(r["workflow_id"],r["instance_id"]))
        full_audit=audit_records(merged)
        if len(merged)!=600 or full_audit["duplicate_rejected"]:
            raise SystemExit(f"full-suite duplicate/quota gate failed: {full_audit}")
        if args.dry_run:
            print(json.dumps({"dry_run":True,"old_manifest_sha256":base_hash,
                "target_workflows":sorted(TARGETS),"replaced_old_instances":sum(map(len,before.values())),
                "new_instances":len(new_rows),"candidate_exact_duplicates":candidate_audit["exact_duplicate_rejected"],
                "candidate_near_duplicates":candidate_audit["near_duplicate_rejected"],
                "candidate_runtime_compiled":compile_result["compiled"]},indent=2))
            return

        # Preserve the pre-refresh provenance/assets before replacing canonical rows.
        SNAPSHOT.mkdir(parents=True)
        for name in ("instances","fixtures","evaluators","workflows"): (SNAPSHOT/name).mkdir()
        old_target=[]
        for wid in sorted(TARGETS):
            shutil.copy2(SUITE/"workflows"/f"{wid}.json",SNAPSHOT/"workflows"/f"{wid}.json")
            old_target.extend(before[wid])
        (SNAPSHOT/"manifest.jsonl").write_text("".join(old_raw[r["instance_id"]][0]+"\n" for r in sorted(old_target,key=lambda r:(r["workflow_id"],r["instance_id"]))))
        for row in old_target:copy_record_assets(row,SUITE,SNAPSHOT)
        old_plans=[json.loads(x) for x in (SUITE/"runtime_plans.jsonl").read_text().splitlines()]
        snapshot_plans=[p for p in old_plans if p["workflow_id"] in TARGETS]
        (SNAPSHOT/"runtime_plans.jsonl").write_text("".join(json.dumps(p,sort_keys=True,separators=(",",":"))+"\n" for p in snapshot_plans))
        snapshot_info={"snapshot_kind":"pre_diversity_refresh","base_manifest_sha256":base_hash,
            "base_git_head":git_commit(ROOT),"affected_workflows":sorted(TARGETS),
            "old_instance_count":len(old_target),"old_instance_ids":[r["instance_id"] for r in sorted(old_target,key=lambda r:r["instance_id"])],
            "old_evaluator_and_fixture_hashes":{r["instance_id"]:{"evaluator_sha256":r["evaluator_sha256"],
                "fixture_sha256":r["signatures"]["fixture"]} for r in old_target},
            "preservation":"original rows, instance manifests, evaluator files, fixtures, workflow definitions and compiled plans"}
        (SNAPSHOT/"snapshot.json").write_text(json.dumps(snapshot_info,indent=2,sort_keys=True)+"\n")

        old_ids={r["instance_id"] for r in old_target}
        for row in old_target:
            shutil.rmtree(SUITE/"instances"/row["instance_id"])
            (SUITE/row["evaluator_path"]).unlink()
            shutil.rmtree(SUITE/"fixtures"/row["instance_id"])
        for row in new_rows:copy_record_assets(row,stage,SUITE)
        for wid in sorted(TARGETS):
            (SUITE/"workflows"/f"{wid}.json").write_text(json.dumps(registry[wid],indent=2,sort_keys=True)+"\n")
        # Non-target manifest lines are copied byte-for-byte from the original file.
        new_by_id={r["instance_id"]:r for r in new_rows}
        output=[]
        for row in merged:
            if row["workflow_id"] not in TARGETS:
                output.append(old_raw[row["instance_id"]][0])
            else:
                output.append(json.dumps(row,sort_keys=True,separators=(",",":")))
        (SUITE/"manifest.jsonl").write_text("\n".join(output)+"\n")
        with tempfile.TemporaryDirectory(prefix="codesk-full-plan-compile-") as plan_tmp:
            compiled_path=Path(plan_tmp)/"runtime_plans.jsonl"
            full_compile=compile_suite(SUITE/"manifest.jsonl",SUITE,compiled_path)
            if full_compile.get("failed") or full_compile.get("compiled")!=600:
                raise SystemExit(f"final runtime compile failed; snapshot retained: {full_compile}")
            full_compile["plans_path"]="benchmarks/codesk_v1_final/runtime_plans.jsonl"
            compiled={json.loads(line)["run_id"]:line for line in compiled_path.read_text().splitlines()}
            prior_lines={json.loads(line)["run_id"]:line for line in (SUITE/"runtime_plans.jsonl").read_text().splitlines()}
            merged_plans=[]
            for row in merged:
                run_id=f"plan-{row['instance_id']}"
                if row["workflow_id"] in TARGETS: merged_plans.append(compiled[run_id])
                else: merged_plans.append(prior_lines[run_id])
            (SUITE/"runtime_plans.jsonl").write_text("\n".join(merged_plans)+"\n")
        old_validation=(SUITE/"metadata"/"validation_manifest.jsonl").read_text().splitlines()
        old_validation_by_w={w:[json.loads(x) for x in old_validation if json.loads(x)["workflow_id"]==w] for w in TARGETS}
        validation=[]
        for line in old_validation:
            row=json.loads(line)
            if row["workflow_id"] not in TARGETS:validation.append(line)
        for wid in sorted(TARGETS):
            for row in sorted([x for x in new_rows if x["workflow_id"]==wid],key=lambda r:r["instance_id"])[:3]:
                validation.append(json.dumps({"workflow_id":wid,"instance_id":row["instance_id"],
                    "semantic_signature":row["signatures"]["semantic"],"fixture_signature":row["signatures"]["fixture"]},sort_keys=True))
        (SUITE/"metadata"/"validation_manifest.jsonl").write_text("\n".join(validation)+"\n")
        generation=json.loads((SUITE/"metadata"/"generation.json").read_text())
        generation.update({"instance_count":600,"workflow_count":30,"family_count":5,
            "manifest_sha256":digest(SUITE/"manifest.jsonl"),"source_commit":git_commit(ROOT),
            "diversity_refresh":{"version":"2026-10-08","affected_workflows":sorted(TARGETS),
                "old_instance_count":len(old_target),"new_instance_count":len(new_rows),
                "snapshot":"benchmarks/codesk_v1_final_history/pre_diversity_refresh_20261008",
                "base_manifest_sha256":base_hash},
            "exact_duplicate_rejected":full_audit["exact_duplicate_rejected"],
            "near_duplicate_rejected":full_audit["near_duplicate_rejected"],
            "duplicate_rejected":full_audit["duplicate_rejected"],
            "positive_oracle_checks":600,"negative_oracle_checks":600,
            "fixture_hash_checks":sum(len(r["fixture_files"]) for r in merged),
            "runtime_plan_compile":full_compile,"runtime_preflight_ready":600,"runtime_preflight_total":600})
        (SUITE/"metadata"/"generation.json").write_text(json.dumps(generation,indent=2,sort_keys=True)+"\n")
        (SUITE/"metadata"/"diversity-audit.json").write_text(json.dumps(full_audit,indent=2,sort_keys=True)+"\n")
        regen={"version":"2026-10-08","source_commit":git_commit(ROOT),"base_manifest_sha256":base_hash,
            "final_manifest_sha256":digest(SUITE/"manifest.jsonl"),"affected_workflows":sorted(TARGETS),
            "replaced_instance_ids":sorted(old_ids),"new_instance_ids":sorted(new_by_id),
             "non_target_workflow_rows_preserved_byte_for_byte":True,"non_target_runtime_plans_preserved_byte_for_byte":True,
            "target_runtime_plans_recompiled":220,"full_runtime_plan_compile_count":600,"guest_or_qwen_started":False}
        (SUITE/"metadata"/"diversity-regeneration.json").write_text(json.dumps(regen,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"updated_manifest_sha256":digest(SUITE/"manifest.jsonl"),
            "replaced":len(old_ids),"new":len(new_rows),"runtime_compiled":full_compile["compiled"],
            "snapshot":str(SNAPSHOT.relative_to(ROOT))},indent=2))
if __name__=="__main__":main()
