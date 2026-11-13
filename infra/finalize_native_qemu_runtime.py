#!/usr/bin/env python3
"""Finish and validate the authorized local native-QEMU execution cache."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path('/tmp/codesk-local-runtime-20261025')
RECORD = Path('/opt/data/private/mjh/runs/codesk/local-runtime-restore-20261025')


def main():
    owner = json.loads((ROOT / 'ownership.json').read_text())
    status = json.loads((ROOT / 'status.json').read_text())
    assert owner['owner'] == 'CoDesk' and owner['uid'] == os.getuid() and not ROOT.is_symlink()
    assert status['status'] in {'COPIED_REBASED_PENDING_MCP', 'PREPARING_MCP_COMPATIBILITY', 'READY'}
    status['status'] = 'PREPARING_MCP_COMPATIBILITY'
    (ROOT / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    old_prefixes = ['/tmp/osworld-native-qemu-venv', '/opt/data/private/mjh/deps/osworld/venv-native-qemu']
    scripts_rebased = []
    for p in (ROOT / 'venv/bin').iterdir():
        if p.is_symlink() or not p.is_file():
            continue
        raw = p.read_bytes()
        if b'\0' in raw:
            continue
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        updated = text
        for prefix in old_prefixes:
            updated = updated.replace(prefix, str(ROOT / 'venv'))
        if updated != text:
            p.write_text(updated)
            scripts_rebased.append(p.name)
    for name in ['tmp', 'uv-cache']:
        (ROOT / name).mkdir(exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(ROOT / 'tmp'), 'UV_CACHE_DIR': str(ROOT / 'uv-cache'),
           'PYTHONPATH': str(ROOT / 'CoDesk') + ':' + str(ROOT / 'OSWorld')}
    command = [str(ROOT / 'bin/uv'), 'pip', 'install', '--python', str(ROOT / 'venv/bin/python'),
               '--default-index', 'https://pypi.org/simple', 'mcp==1.12.4', 'pydantic>=2.8,<2.12',
               'starlette==0.47.3', 'sse-starlette<3', 'python-dotenv==1.1.1']
    subprocess.run(command, env=env, check=True, timeout=240)
    dependency_check = subprocess.run([str(ROOT / 'bin/uv'), 'pip', 'check', '--python', str(ROOT / 'venv/bin/python')],
                                      env=env, capture_output=True, text=True, timeout=60)
    (ROOT / 'dependency-check.log').write_text(dependency_check.stdout + dependency_check.stderr)
    if dependency_check.returncode:
        raise RuntimeError(f'dependency compatibility check failed; inspect {ROOT}/dependency-check.log')
    probe = r'''
import json,sys,os,importlib.metadata
from pathlib import Path
root=Path('/tmp/codesk-local-runtime-20261025')
os.chdir(root/'OSWorld')
import pandas,gymnasium,mcp
from mcp.server.fastmcp import FastMCP
import oscombo.desktop_tools,oscombo.native_qemu
from desktop_env.desktop_env import DesktopEnv
bad={name:m.__file__ for name,m in list(sys.modules.items()) if isinstance(getattr(m,'__file__',None),str) and m.__file__.startswith('/opt/data/private/mjh')}
assert not bad, bad
assert not any(p.startswith('/opt/data/private/mjh') for p in sys.path),sys.path
print(json.dumps({'python':sys.executable,'base_prefix':sys.base_prefix,'mcp':importlib.metadata.version('mcp'),'pydantic':importlib.metadata.version('pydantic'),'pandas':pandas.__version__,'gymnasium':gymnasium.__version__,'loaded_modules_from_LeoFS':bad}))
'''
    result = subprocess.run([str(ROOT / 'venv/bin/python'), '-c', probe], env=env,
                            capture_output=True, text=True, timeout=180)
    (ROOT / 'import-probe.stdout').write_text(result.stdout)
    (ROOT / 'import-probe.stderr').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f'local import probe failed; inspect {ROOT}/import-probe.stderr')
    details = json.loads(result.stdout.strip().splitlines()[-1])
    versions = {}
    for name, command in {
        'qemu': [str(ROOT / 'qemu/bin/qemu-system-x86_64'), '--version'],
        'qemu_img': [str(ROOT / 'qemu/bin/qemu-img'), '--version'],
        'codex': [str(ROOT / 'bin/codex'), '--version'],
    }.items():
        versions[name] = subprocess.check_output(command, env=env, text=True, timeout=30).splitlines()[0]
    image = json.loads(subprocess.check_output([str(ROOT / 'qemu/bin/qemu-img'), 'info', '--output=json',
                       str(ROOT / 'image/base.qcow2')], env=env, text=True, timeout=30))
    assert not image.get('backing-filename'), image
    allocated = sum(p.lstat().st_blocks * 512 for base, dirs, files in os.walk(ROOT)
                    for p in [*(Path(base) / name for name in files)])
    assert allocated <= owner['size_limit_bytes'], f'local cache exceeds limit: {allocated}'
    status.update({'status': 'READY', 'validated_unix': time.time(), 'imports': details,
                   'versions': versions, 'image_info': image, 'allocated_bytes': allocated,
                   'console_scripts_rebased': sorted(set(status.get('console_scripts_rebased', []) + scripts_rebased)),
                   'dependency_check': 'PASS',
                   'credentials_in_local_cache': False})
    (ROOT / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    RECORD.mkdir(parents=True, exist_ok=True)
    for name in ['status.json', 'import-probe.stdout', 'import-probe.stderr']:
        for attempt in range(5):
            try:
                shutil.copyfile(ROOT / name, RECORD / name)
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(1)
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
