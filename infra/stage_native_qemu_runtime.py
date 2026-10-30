#!/usr/bin/env python3
"""Prepare a verified, owned local execution cache from persistent CoDesk copies."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

PRIVATE = Path('/opt/data/private/mjh')
ROOT = Path('/tmp/codesk-local-runtime-20261025')
IMAGE_SHA = '28b617987f3edf14edd835069cdde6a6e4708be8e4ae4eb957200d5da335186a'
RECORD = PRIVATE / 'runs/codesk/local-runtime-restore-20261025'
SKIP = {'__pycache__', '.git', '.pytest_cache'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def retry(operation):
    for attempt in range(5):
        try:
            return operation()
        except OSError as exc:
            if exc.errno not in {5, 107, 116} or attempt == 4:
                raise
            time.sleep(min(2, 0.25 * 2 ** attempt))


def save(name, value):
    p = ROOT / name
    tmp = p.with_name(p.name + '.new')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, p)


def main():
    os.umask(0o077)
    if ROOT.is_symlink():
        raise SystemExit('local runtime root must not be a symlink')
    if ROOT.exists():
        owner = json.loads((ROOT / 'ownership.json').read_text())
        assert owner['owner'] == 'CoDesk' and owner['uid'] == os.getuid()
        previous = ROOT / 'status.json'
        if previous.exists():
            state = json.loads(previous.read_text())
            if state.get('status') in {'READY', 'COPIED_REBASED_PENDING_MCP', 'PREPARING_MCP_COMPATIBILITY'}:
                print(json.dumps({'existing_cache': str(ROOT), 'status': state['status'],
                                  'action': 'retained; finalize if needed; code snapshot is versioned'}), flush=True)
                return 0
    else:
        ROOT.mkdir(mode=0o700)
        save('ownership.json', {'owner': 'CoDesk', 'uid': os.getuid(),
             'purpose': 'verified local execution cache; persistent originals retained',
             'created_unix': time.time(), 'size_limit_bytes': 25 * 1024**3})
    if shutil.disk_usage(ROOT).free < 22 * 1024**3:
        raise SystemExit('less than 22 GiB local free space; stopping')
    manifest_path = ROOT / 'copy-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    counts = {'copied': 0, 'verified_existing': 0, 'bytes_copied': 0}
    errors = []
    started = time.monotonic()
    save('status.json', {'status': 'COPYING', 'started_unix': time.time()})

    def copy_file(source, target, expected=None):
        meta = retry(source.stat)
        rel = str(target.relative_to(ROOT))
        prior = manifest.get(rel)
        if target.is_file() and not target.is_symlink() and prior:
            if target.stat().st_size == meta.st_size and digest(target) == prior['sha256']:
                if prior['source_size'] == meta.st_size and prior['source_mtime_ns'] == meta.st_mtime_ns:
                    if expected is None or prior['sha256'] == expected:
                        counts['verified_existing'] += 1
                        return
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.copy-part')
        offset = partial.stat().st_size if expected and partial.exists() else 0
        if offset > meta.st_size:
            offset = 0
        hasher = hashlib.sha256()
        # A resumed image has a known full SHA; other files restart hashing.
        if not expected:
            offset = 0
        with partial.open('r+b' if partial.exists() else 'w+b') as out:
            out.truncate(offset)
            for attempt in range(5):
                try:
                    with source.open('rb') as inp:
                        inp.seek(offset)
                        out.seek(offset)
                        while block := inp.read(1024 * 1024):
                            out.write(block)
                            if not expected:
                                hasher.update(block)
                            offset += len(block)
                            counts['bytes_copied'] += len(block)
                    break
                except OSError as exc:
                    out.flush()
                    if exc.errno not in {5, 107, 116} or attempt == 4:
                        raise
                    print(json.dumps({'retry_file': rel, 'errno': exc.errno,
                                      'attempt': attempt + 1, 'offset': offset}), flush=True)
                    time.sleep(min(2, 0.25 * 2**attempt))
        assert offset == meta.st_size, f'incomplete copy: {rel}'
        copied_sha = digest(partial)
        assert copied_sha == (expected or hasher.hexdigest()), f'checksum mismatch: {rel}'
        after = retry(source.stat)
        assert (after.st_size, after.st_mtime_ns) == (meta.st_size, meta.st_mtime_ns), f'source changed: {rel}'
        os.chmod(partial, stat.S_IMODE(meta.st_mode))
        os.utime(partial, ns=(meta.st_atime_ns, meta.st_mtime_ns))
        os.replace(partial, target)
        manifest[rel] = {'sha256': copied_sha, 'source': str(source),
                         'source_size': meta.st_size, 'source_mtime_ns': meta.st_mtime_ns}
        counts['copied'] += 1
        if counts['copied'] % 250 == 0:
            save('copy-manifest.json', manifest)
            print(json.dumps({'progress': counts, 'last_file': rel}), flush=True)

    def tree(source, target, code_only=False):
        try:
            entries = retry(lambda: list(source.iterdir()))
        except OSError as exc:
            errors.append({'path': str(source), 'errno': exc.errno, 'operation': 'listdir'})
            return
        target.mkdir(parents=True, exist_ok=True)
        for p in entries:
            if p.name in SKIP:
                continue
            dest = target / p.name
            try:
                info = retry(p.lstat)
                if stat.S_ISLNK(info.st_mode):
                    link = retry(lambda: os.readlink(p))
                    if dest.is_symlink() and os.readlink(dest) == link:
                        continue
                    if dest.exists() or dest.is_symlink():
                        raise RuntimeError(f'unexpected existing link destination: {dest}')
                    dest.symlink_to(link)
                elif stat.S_ISDIR(info.st_mode):
                    tree(p, dest, code_only)
                elif stat.S_ISREG(info.st_mode) and (not code_only or p.suffix in {'.py', '.ts'}):
                    copy_file(p, dest)
            except OSError as exc:
                errors.append({'path': str(p), 'errno': exc.errno, 'operation': 'copy'})

    items = [
        (PRIVATE / 'deps/uv/python/cpython-3.12.15-linux-x86_64-gnu', ROOT / 'python', False),
        (PRIVATE / 'deps/osworld/venv-native-qemu', ROOT / 'venv', False),
        (PRIVATE / 'deps/qemu/jammy-6.2/root', ROOT / 'qemu', False),
        (PRIVATE / 'OSWorld-V2/desktop_env', ROOT / 'OSWorld/desktop_env', False),
        (PRIVATE / 'projects/CoDesk/oscombo', ROOT / 'CoDesk/oscombo', True),
        (PRIVATE / 'projects/CoDesk/infra', ROOT / 'CoDesk/infra', True),
    ]
    for attempt in range(3):
        errors.clear()
        for source, target, code_only in items:
            tree(source, target, code_only)
            save('copy-manifest.json', manifest)
            print(json.dumps({'tree_done': str(target), 'errors': len(errors), 'counts': counts}), flush=True)
        if not errors:
            break
        save('copy-errors.json', errors)
        print(json.dumps({'tree_pass': attempt + 1, 'errors': len(errors)}), flush=True)
    if errors:
        save('status.json', {'status': 'BLOCKED_COPY', 'errors': errors, 'counts': counts})
        return 2

    for source, target, expected in [
        (PRIVATE / 'deps/osworld/images/osworld-v2-ubuntu-x86.qcow2', ROOT / 'image/base.qcow2', IMAGE_SHA),
        ((PRIVATE / 'tools/bin/codex').resolve(), ROOT / 'bin/codex', None),
        (PRIVATE / 'projects/CoDesk/.venv/bin/uv', ROOT / 'bin/uv', None),
    ]:
        copy_file(source, target, expected)
        save('copy-manifest.json', manifest)
        print(json.dumps({'file_done': str(target), 'counts': counts}), flush=True)

    # Rebase only owned working copies. Preserve persistent environments intact.
    python_link = ROOT / 'venv/bin/python'
    if python_link.is_symlink():
        python_link.unlink()
    python_link.symlink_to(ROOT / 'python/bin/python3.12')
    cfg = ROOT / 'venv/pyvenv.cfg'
    original_home = str(PRIVATE / 'deps/uv/python/cpython-3.12.15-linux-x86_64-gnu/bin')
    cfg.write_text(cfg.read_text().replace(original_home, str(ROOT / 'python/bin')))
    for name in ['qemu-system-x86_64', 'qemu-img']:
        wrapper = ROOT / 'qemu/bin' / name
        wrapper.write_text(wrapper.read_text().replace(str(PRIVATE / 'deps/qemu/jammy-6.2/root'), str(ROOT / 'qemu')))
        wrapper.chmod(0o700)
    (ROOT / 'image/base.qcow2').chmod(0o400)
    external_links = []
    for base in [ROOT / 'venv', ROOT / 'python', ROOT / 'qemu']:
        for current, dirs, files in os.walk(base):
            for name in dirs + files:
                p = Path(current) / name
                if p.is_symlink():
                    target = os.readlink(p)
                    if target.startswith(str(PRIVATE)):
                        external_links.append({'path': str(p), 'target': target})
    save('external-links.json', external_links)
    if external_links:
        save('status.json', {'status': 'BLOCKED_EXTERNAL_LINKS', 'links': external_links})
        return 2
    save('status.json', {'status': 'COPIED_REBASED_PENDING_MCP', 'counts': counts,
         'image_sha256': IMAGE_SHA, 'elapsed_s': round(time.monotonic() - started, 3)})
    RECORD.mkdir(parents=True, exist_ok=True)
    for name in ['ownership.json', 'status.json', 'copy-manifest.json', 'external-links.json']:
        retry(lambda name=name: shutil.copyfile(ROOT / name, RECORD / name))
    print(json.dumps(json.loads((ROOT / 'status.json').read_text())), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
