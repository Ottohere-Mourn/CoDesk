#!/usr/bin/env bash
set -euo pipefail

uid="${CODESK_NFS_ANON_UID:?CODESK_NFS_ANON_UID is required}"
gid="${CODESK_NFS_ANON_GID:?CODESK_NFS_ANON_GID is required}"
[[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || {
  echo 'NFS anonymous uid/gid must be numeric' >&2
  exit 2
}
for path in /exports/task /exports/reset; do
  [[ -d "$path" && -r "$path" && -w "$path" && -x "$path" ]] || {
    echo "NFS export path is not accessible: $path" >&2
    exit 3
  }
done
sed -e "s/__ANON_UID__/$uid/g" -e "s/__ANON_GID__/$gid/g" \
  /etc/ganesha/ganesha.conf.template > /run/ganesha.conf
# Ganesha registers RPC services with the container-local portmapper. Keep
# rpcbind isolated inside this project container; do not publish its port.
/usr/sbin/rpcbind -f -w >/run/rpcbind.log 2>&1 &
rpcbind_pid=$!
for _ in $(seq 1 30); do
  [[ -S /run/rpcbind.sock ]] && break
  sleep 0.1
done
if ! kill -0 "$rpcbind_pid" 2>/dev/null; then
  cat /run/rpcbind.log >&2
  exit 4
fi
if [[ -x /usr/bin/dbus-daemon && -f /etc/dbus-1/system.conf ]]; then
  /usr/bin/dbus-daemon --system --fork --nopidfile || true
fi
exec /usr/bin/ganesha.nfsd -F -L STDOUT -f /run/ganesha.conf
