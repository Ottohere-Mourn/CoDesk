"""Check host and rootless-container KVM access without booting a Guest or changing permissions."""
import argparse
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import secrets
import stat
import subprocess
import sys
from datetime import datetime, timezone


def host_probe():
    user = pwd.getpwuid(os.getuid()).pw_name
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'host': os.uname().nodename,
        'user': user, 'uid': os.getuid(), 'session_groups': os.getgroups(),
        'nss_groups': os.getgrouplist(user, os.getgid()), 'device': {}}
    try:
        device = Path('/dev/kvm').stat()
        result['device'] = {'exists': True, 'mode': stat.filemode(device.st_mode), 'uid': device.st_uid,
            'gid': device.st_gid, 'group': grp.getgrgid(device.st_gid).gr_name}
        descriptor = os.open('/dev/kvm', os.O_RDWR | os.O_CLOEXEC)
        try:
            result['device']['api_version'] = fcntl.ioctl(descriptor, 0xAE00, 0)
            result['device']['open_read_write'] = True
        finally:
            os.close(descriptor)
    except OSError as error:
        result['device'].update(open_read_write=False, errno=error.errno, error=error.strerror)
    result['kvm_modules'] = [line.split()[0] for line in Path('/proc/modules').read_text().splitlines() if line.startswith('kvm')]
    result['cpu_virtualization_flags'] = sorted(set(('svm', 'vmx')) & set(Path('/proc/cpuinfo').read_text().split()))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--safety-source', type=Path, required=True)
    parser.add_argument('--image', default='paragui/weavebench-pairs:20261103')
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.safety_source))
    from swcub.resource_safety import ResourceIdentity, ResourceLedger
    from scripts.cleanup_owned_resources import clean_one
    ledger = ResourceLedger(args.out / 'resource-events.jsonl')
    identity = ResourceIdentity('codesk-kvm-' + secrets.token_hex(8), secrets.token_hex(32), ledger.path)
    ledger.record('run_started', 'run', identity.run_id, identity)
    result = {'host_probe': host_probe(), 'container_probe': {}, 'guest_boots': 0, 'task_model_episodes': 0,
        'permission_changes': False, 'privileged_container': False}
    code = """import fcntl,json,os
result={'uid':os.getuid(),'groups':os.getgroups()}
try:
    descriptor=os.open('/dev/kvm',os.O_RDWR|os.O_CLOEXEC)
    try:
        result['api_version']=fcntl.ioctl(descriptor,0xAE00,0)
        result['open_read_write']=True
    finally:
        os.close(descriptor)
except OSError as error:
    result.update(open_read_write=False,errno=error.errno,error=error.strerror)
print(json.dumps(result))
"""
    command = ['docker', 'create', '--name', identity.run_id, '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '128m', '--cpus', '.25',
        '--pids-limit', '32', '--device', '/dev/kvm:/dev/kvm']
    for name, value in identity.labels.items():
        command += ['--label', name + '=' + value]
    command += [args.image, 'python3', '-c', code]
    container_id = None
    try:
        created = subprocess.run(command, capture_output=True, text=True, timeout=30)
        result['container_probe']['create_exit_code'] = created.returncode
        if created.returncode:
            result['container_probe']['create_error'] = created.stderr.strip()
        else:
            container_id = created.stdout.strip()
            ledger.created_container(container_id, identity, name=identity.run_id, image=args.image)
            result['container_probe']['container_id'] = container_id
            started = subprocess.run(['docker', 'start', '-a', container_id], capture_output=True, text=True, timeout=30)
            result['container_probe'].update(start_exit_code=started.returncode, stderr=started.stderr.strip())
            if started.stdout.strip():
                result['container_probe']['device_probe'] = json.loads(started.stdout)
    except Exception as error:
        result['container_probe']['probe_error'] = f'{type(error).__name__}: {error}'
    finally:
        if container_id:
            try:
                result['container_probe']['cleanup'] = clean_one(ledger.path, container_id, apply=True)
            except Exception as error:
                result['container_probe']['cleanup_error'] = str(error)
        (args.out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
