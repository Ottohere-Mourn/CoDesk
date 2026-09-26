#!/usr/bin/env bash
set -euo pipefail

base_image="${OSWORLD_VM_IMAGE:-/System.qcow2}"
overlay="${OSWORLD_VM_OVERLAY:-/tmp/osworld-v2.1-overlay.qcow2}"
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

exec qemu-system-x86_64 \
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
