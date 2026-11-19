"""Build run-owned MECH-01 Guest assets; never overwrite run results."""
from pathlib import Path
import hashlib, json, shutil, sys
ROOT=Path(__file__).resolve().parents[2]
DEST=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
target=DEST/"mechanism_expansion_v1"/"mech01";target.mkdir(parents=True,exist_ok=True)
src=ROOT/"tasks"/"mechanism_expansion_v1"/"mech01"/"app.py"
out=target/"app.py";shutil.copyfile(src,out)
manifest={"case_id":"MECH-01","task_version":"0.1.4","files":{"app.py":hashlib.sha256(out.read_bytes()).hexdigest()}}
(target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps({"assets":str(target),"manifest":manifest},indent=2))
