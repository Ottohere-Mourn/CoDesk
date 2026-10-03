#!/usr/bin/env python3
"""Generate the offline-only 30-workflow CoDesk fixed suite; never starts a Guest."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import (DOMAINS, FAMILIES, LAYOUTS, _PROFILE_ROWS, build_instance,
    materialize, audit_records, canonical_bytes, sha256, read_manifest, evaluate_oracle,
    _positive_state, _negative_state, workflow_registry, git_commit)
from swcub.runtime_v1 import compile_suite
from swcub.runtime_bindings_v1 import build_runtime_binding_registry

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUT=ROOT/'benchmarks/codesk_v1_final'
OLD_ROOT=ROOT/'benchmarks/codesk_v1'

def generate(output:Path,seed:int):
    output=output.resolve()
    if output.exists(): raise FileExistsError(f"refusing to overwrite existing suite: {output}")
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.codesk-final-v1-',dir=output.parent))
    try:
        for name in ('families','workflows','instances','fixtures','evaluators','metadata'):(stage/name).mkdir()
        workflows=workflow_registry()
        if len(workflows)!=30: raise RuntimeError(f"expected 30 registered workflows, found {len(workflows)}")
        by_id={row['workflow_id']:row for row in workflows}
        for family_id,label in FAMILIES.items():
            (stage/'families'/f'{family_id}.json').write_text(json.dumps({'family_id':family_id,'label':label,'benchmark_version':'codesk-v1.1-offline-final'},indent=2)+'\n')
        records=[]
        layout=next(x for x in LAYOUTS if x['id']=='guard_after')
        for wid in sorted(by_id):
            workflow=by_id[wid]
            (stage/'workflows'/f'{wid}.json').write_text(json.dumps(workflow,indent=2,sort_keys=True)+'\n')
            profiles=_PROFILE_ROWS[wid]
            if len(profiles)!=5: raise RuntimeError(f'{wid}: expected five distinct object profiles, got {len(profiles)}')
            for domain in DOMAINS:
                for profile in profiles:
                    spec=build_instance(wid,domain,profile,layout,seed,ROOT)
                    row=materialize(spec,stage)
                    ev=json.loads((stage/row['evaluator_path']).read_text())
                    if not evaluate_oracle({'workflow_id':wid,'evaluator':ev},_positive_state(spec))['joint_success']:
                        raise RuntimeError(f"positive evaluator gate failed: {wid}/{row['instance_id']}")
                    if evaluate_oracle({'workflow_id':wid,'evaluator':ev},_negative_state(spec))['joint_success']:
                        raise RuntimeError(f"negative evaluator gate failed: {wid}/{row['instance_id']}")
                    for asset in row['fixture_files']:
                        if sha256((stage/asset['path']).read_bytes())!=asset['sha256']:
                            raise RuntimeError(f"fixture hash mismatch: {asset['path']}")
                    records.append(row)
        records.sort(key=lambda r:(r['workflow_id'],r['instance_id']))
        audit=audit_records(records)
        if audit['duplicate_rejected']:
            raise RuntimeError(f"duplicate gate failed: {audit['duplicate_rejected']}")
        (stage/'manifest.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n' for r in records))
        # Keep a compact, stable validation subset that points into the fixed suite.
        validation=[]
        for wid in sorted(by_id):
            validation.extend([r for r in records if r['workflow_id']==wid][:3])
        (stage/'metadata'/'validation_manifest.jsonl').write_text(''.join(json.dumps({'workflow_id':r['workflow_id'],'instance_id':r['instance_id'],'semantic_signature':r['signatures']['semantic'],'fixture_signature':r['signatures']['fixture']},sort_keys=True)+'\n' for r in validation))
        compile_result=compile_suite(stage/'manifest.jsonl',stage,stage/'runtime_plans.jsonl')
        compile_result['plans_path']=str(output.relative_to(ROOT)/'runtime_plans.jsonl') if ROOT in output.parents else str(output/'runtime_plans.jsonl')
        if compile_result.get('failed') or compile_result.get('compiled')!=len(records):
            raise RuntimeError(f"runtime plan compilation incomplete: {compile_result}")
        missing=[];binding_registry=build_runtime_binding_registry()
        for plan_line in (stage/'runtime_plans.jsonl').read_text().splitlines():
            plan=json.loads(plan_line); wid=plan['workflow_id']; bind=plan['runtime_execution_binding']
            if bind.get('missing_components'):missing.append((wid,bind['missing_components']))
            obj=binding_registry.get(wid,{})
            if not all(callable(obj.get(k)) for k in ('setup','initial_verifier','evaluator','event_gate')):missing.append((wid,'callable binding'))
        if missing: raise RuntimeError(f"MISSING_IMPLEMENTATION {len(missing)}: {missing[:5]}")
        per={wid:sum(r['workflow_id']==wid for r in records) for wid in sorted(by_id)}
        families={f:sum(row['family']==f for row in workflows) for f in FAMILIES}
        old_manifest=OLD_ROOT/'manifest.jsonl'
        snapshot={'path':'benchmarks/codesk_v1','classification':'prototype_previous_production_snapshot','workflow_count':15,'instance_count':600,
          'manifest_sha256':hashlib.sha256(old_manifest.read_bytes()).hexdigest() if old_manifest.is_file() else None,
          'source_generation_metadata':str((OLD_ROOT/'metadata'/'generation.json').relative_to(ROOT)) if (OLD_ROOT/'metadata'/'generation.json').is_file() else None}
        (stage/'metadata'/'prototype_snapshot.json').write_text(json.dumps(snapshot,indent=2,sort_keys=True)+'\n')
        metadata={'benchmark_version':'codesk-v1.1-offline-final','status':'OFFLINE_FINAL_SUITE_READY','guest_or_qwen_run':False,
          'generation_seed':seed,'workflow_count':len(by_id),'family_count':len(families),'instance_count':len(records),
          'quota_by_workflow':per,'family_workflow_counts':families,'source_commit':git_commit(ROOT),
          'manifest_sha256':hashlib.sha256((stage/'manifest.jsonl').read_bytes()).hexdigest(),
          'runtime_plan_compile':compile_result,'runtime_preflight_ready':len(records),'runtime_preflight_total':len(records),
          'missing_implementation':0,'exact_duplicate_rejected':audit['exact_duplicate_rejected'],
          'near_duplicate_rejected':audit['near_duplicate_rejected'],'duplicate_rejected':audit['duplicate_rejected'],
          'positive_oracle_checks':len(records),'negative_oracle_checks':len(records),'fixture_hash_checks':sum(len(r['fixture_files']) for r in records),
          'validation_subset_count':len(validation),'evidence_boundary':'offline schema/generator/oracle/binding/fake lifecycle only; no real Guest/Qwen validation'}
        (stage/'metadata'/'generation.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
        (stage/'metadata'/'diversity-audit.json').write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
        if len(validation)!=90 or len(records)!=600 or min(per.values())!=20 or max(per.values())!=20:raise RuntimeError('suite quota gate failed')
        stage.rename(output)
        return metadata
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=DEFAULT_OUT);ap.add_argument('--seed',type=int,default=2026);args=ap.parse_args()
    print(json.dumps(generate(args.output,args.seed),indent=2,sort_keys=True))
