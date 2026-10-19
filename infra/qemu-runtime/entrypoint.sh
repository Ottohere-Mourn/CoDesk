#!/usr/bin/env bash
# Boot the read-only base image through a fresh qcow2 overlay. Env (set by the patched docker provider):
#   OSWORLD_VM_IMAGE (default /System.qcow2), OSWORLD_VM_OVERLAY (default /tmp/...), RAM_SIZE, CPU_CORES,
#   TCG_CPU_MODEL (only without /dev/kvm).
set -euo pipefail

base_image="${OSWORLD_VM_IMAGE:-/System.qcow2}"
overlay="${OSWORLD_VM_OVERLAY:-/tmp/osworld-overlay.qcow2}"
if [[ ! -r "$base_image" ]]; then
  echo "OSWorld base image is not readable: $base_image" >&2
  exit 2
fi
# Without /dev/kvm (e.g. nested containers) fall back to TCG software emulation. The default TCG CPU model
# breaks the Guest's llvmpipe (gnome-shell aborts -> black screen); a named model such as Haswell-noTSX works.
# QEMU 6.2 rejects thread= inside -machine, so the accelerator goes through -accel.
if [[ -r /dev/kvm ]]; then
  accel="kvm"
  cpu="host"
else
  echo "WARNING: /dev/kvm is not readable; using TCG software emulation (much slower)" >&2
  accel="tcg,thread=multi"
  cpu="${TCG_CPU_MODEL:-Haswell-noTSX}"
fi

qemu-img create -q -f qcow2 -F qcow2 -b "$base_image" "$overlay"

exec qemu-system-x86_64 \
  -machine pc \
  -accel "$accel" \
  -cpu "$cpu" \
  -m "${RAM_SIZE:-4G}" \
  -smp "${CPU_CORES:-4}" \
  -rtc base=utc \
  -drive "file=$overlay,format=qcow2,if=ide,index=0" \
  -netdev user,id=net0,restrict=off,hostfwd=tcp:0.0.0.0:5000-:5000,hostfwd=tcp:0.0.0.0:8006-:8006,hostfwd=tcp:0.0.0.0:8080-:8080,hostfwd=tcp:0.0.0.0:9222-:9222 \
  -device e1000,netdev=net0 \
  -vga std \
  -display none \
  -monitor none \
  -serial file:/tmp/osworld-serial.log \
  -no-reboot \
  -boot order=c
