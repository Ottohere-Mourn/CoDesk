#!/usr/bin/env bash
set -euo pipefail

base_image="${OSWORLD_VM_IMAGE:-/System.qcow2}"
overlay="${OSWORLD_VM_OVERLAY:-${SWCUB_VM_OVERLAY:-/tmp/osworld-v2.1-overlay.qcow2}}"
if [[ ! -r "$base_image" ]]; then
  echo "OSWorld base image is not readable: $base_image" >&2
  exit 2
fi
if [[ ! -r /dev/kvm ]]; then
  echo "KVM is required for this runtime; /dev/kvm is not readable" >&2
  exit 2
fi

ram="${RAM_SIZE:-4G}"
cpus="${CPU_CORES:-4}"
qemu-img create -q -f qcow2 -F qcow2 -b "$base_image" "$overlay"

qemu_extra=()
shared_workspace="${SWCUB_VM_SHARED_WORKSPACE:-}"
shared_tag="${SWCUB_VM_SHARED_WORKSPACE_TAG:-codesk_workspace}"
if [[ -n "$shared_workspace" ]]; then
  if [[ ! -d "$shared_workspace" ]]; then
    echo "Shared workspace export is not a directory: $shared_workspace" >&2
    exit 3
  fi
  if [[ ! "$shared_tag" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Invalid shared workspace mount tag" >&2
    exit 3
  fi
  qemu_extra=(-virtfs "local,path=${shared_workspace},mount_tag=${shared_tag},security_model=none,id=${shared_tag}")
fi

exec qemu-system-x86_64 \
  "${qemu_extra[@]}" \
  -machine pc,accel=kvm \
  -cpu host \
  -m "$ram" \
  -smp "$cpus" \
  -rtc base=utc \
  -drive "file=$overlay,format=qcow2,if=ide,index=0" \
  -netdev user,id=net0,restrict=off,hostfwd=tcp:0.0.0.0:5000-:5000,hostfwd=tcp:0.0.0.0:8006-:8006,hostfwd=tcp:0.0.0.0:8080-:8080,hostfwd=tcp:0.0.0.0:9222-:9222 \
  -device e1000,netdev=net0 \
  -vga std \
  -display none \
  -monitor none \
  -serial file:/tmp/osworld-v2.1-serial.log \
  -no-reboot \
  -boot order=c
