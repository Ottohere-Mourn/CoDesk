#!/usr/bin/env bash
# Derive a Guest image whose screenshot server skips PNG optimize=True.
#
# Why: the OSWorld-V2 Guest server encodes every screenshot with PNG optimize=True. That is lossless but costs
# ~20 s per frame under QEMU TCG (no KVM); without it a frame takes 1-4 s. Pixels are identical, so agents and
# evaluators see the same images. Not needed with KVM.
#
# How: boot the pristine image through an overlay, edit /home/user/server/src/capture.py in the Guest via its
# /execute endpoint, shut the Guest down cleanly, commit the overlay into a copy of the base image.
#
#   OSCOMBO_RUNTIME_IMAGE=oscombo/qemu-runtime:local bash infra/make_pngfast_image.sh BASE.qcow2 OUT.qcow2
set -euo pipefail
BASE="$(realpath "$1")"; OUT="$(realpath -m "$2")"
IMAGE="${OSCOMBO_RUNTIME_IMAGE:-oscombo/qemu-runtime:local}"
PORT="${PATCH_PORT:-15901}"
PASSWORD="${OSWORLD_CLIENT_PASSWORD:-osworld-public-evaluation}"
WORK="$(dirname "$OUT")/.pngfast-work"; NAME="oscombo-pngfast-$$"
mkdir -p "$WORK"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -f "$WORK/patch.qcow2"; }
trap cleanup EXIT

cp --sparse=always "$BASE" "$OUT"
docker run -d --name "$NAME" -e RAM_SIZE=8G -e CPU_CORES=8 -e OSWORLD_VM_OVERLAY=/work/patch.qcow2 \
  -v "$OUT:/System.qcow2:ro" -v "$WORK:/work" -p "127.0.0.1:$PORT:5000" "$IMAGE" >/dev/null
echo "booting Guest (up to 30 min under TCG)..."
for _ in $(seq 1 180); do
  curl -s -m 60 -o /dev/null -w '%{http_code}' "localhost:$PORT/screenshot" 2>/dev/null | grep -q 200 && break
  sleep 10
done

python3 - "$PORT" <<'PY'
import json, sys, urllib.request
code = r'''
p = "/home/user/server/src/capture.py"; s = open(p).read()
old = '    elif normalized_format == "PNG":\n        save_kwargs["optimize"] = True\n        mime_type = "image/png"'
new = '    elif normalized_format == "PNG":\n        # optimize=True is lossless but ~20 s per frame under QEMU TCG; pixels are identical without it\n        mime_type = "image/png"'
assert s.count(old) == 1, "capture.py pattern not found (different Guest image version?)"
open(p, "w").write(s.replace(old, new))
import glob, os
for f in glob.glob("/home/user/server/src/__pycache__/capture*.pyc"):
    os.remove(f)
print("patched")
'''
body = json.dumps({"command": ["/home/user/server/.venv/bin/python", "-c", code], "shell": False}).encode()
req = urllib.request.Request(f"http://localhost:{sys.argv[1]}/execute", body, {"Content-Type": "application/json"})
out = json.loads(urllib.request.urlopen(req, timeout=120).read())
print(out)
assert "patched" in (out.get("output") or ""), "patch failed"
PY

curl -s -m 60 -H 'content-type: application/json' \
  -d "{\"command\":[\"bash\",\"-c\",\"sync; (sleep 2; echo $PASSWORD | sudo -S poweroff) >/dev/null 2>&1 &\"],\"shell\":false}" \
  "localhost:$PORT/execute" >/dev/null
for _ in $(seq 1 60); do [[ "$(docker inspect -f '{{.State.Running}}' "$NAME")" == "false" ]] && break; sleep 10; done
docker run --rm --entrypoint qemu-img -v "$OUT:/System.qcow2" -v "$WORK:/work" "$IMAGE" commit /work/patch.qcow2
docker run --rm --entrypoint qemu-img -v "$OUT:/System.qcow2:ro" "$IMAGE" check /System.qcow2 | tail -1
echo "done: $OUT  (export OSCOMBO_GUEST_IMAGE=$OUT)"
