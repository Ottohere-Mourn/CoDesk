#!/usr/bin/env bash
# Download/extract QEMU and its Ubuntu 20.04 runtime dependencies into a private prefix.
# This does not install system packages or require sudo.
set -euo pipefail

PREFIX="${OSCOMBO_QEMU_PREFIX:-/opt/data/private/mjh/deps/qemu/ubuntu-focal}"
DEBS="${OSCOMBO_QEMU_DEB_DIR:-/opt/data/private/mjh/deps/qemu/deb-cache-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$PREFIX" "$DEBS"
for tool in apt-get dpkg-deb ldd; do
  command -v "$tool" >/dev/null || { echo "missing host tool: $tool" >&2; exit 2; }
done

packages=(
  qemu-system-x86 qemu-utils qemu-system-common qemu-system-data qemu-block-extra
  ovmf seabios ipxe-qemu ipxe-qemu-256k-compat-efi-roms
  libslirp0 libaio1 libfdt1 libvirglrenderer1 libbrlapi0.7 libcacard0 libusbredirparser1
  librdmacm1 libibverbs1 libspice-server1 libpmem1
)
(cd "$DEBS" && apt-get download "${packages[@]}")
for package in "$DEBS"/*.deb; do
  if ! dpkg-deb --contents "$package" >/dev/null 2>&1; then
    echo "skipping invalid package download (will verify required QEMU runtime below): $package" >&2
    continue
  fi
  dpkg-deb --extract "$package" "$PREFIX"
done

# Ubuntu packages keep SeaBIOS ROMs in a separate directory. QEMU's -L directory
# must also contain them when the packages are unpacked without dpkg maintainer scripts.
qemu_data="$PREFIX/usr/share/qemu"
seabios_data="$PREFIX/usr/share/seabios"
mkdir -p "$qemu_data"
if [[ -d "$seabios_data" ]]; then
  for rom in "$seabios_data"/bios*.bin "$seabios_data"/vgabios-*.bin; do
    [[ -e "$rom" ]] || continue
    target="$qemu_data/$(basename "$rom")"
    [[ -e "$target" ]] || ln -s "../seabios/$(basename "$rom")" "$target"
  done
fi
ipxe_data="$PREFIX/usr/lib/ipxe/qemu"
if [[ -d "$ipxe_data" ]]; then
  for rom in "$ipxe_data"/*.rom; do
    [[ -e "$rom" ]] || continue
    target="$qemu_data/$(basename "$rom")"
    [[ -e "$target" ]] || ln -s "../../lib/ipxe/qemu/$(basename "$rom")" "$target"
  done
fi

runtime_libs="$PREFIX/usr/lib/x86_64-linux-gnu:$PREFIX/usr/lib:$PREFIX/lib/x86_64-linux-gnu:$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
runtime_env=(env "LD_LIBRARY_PATH=$runtime_libs")
missing=""
for executable in "$PREFIX/usr/bin/qemu-system-x86_64" "$PREFIX/usr/bin/qemu-img"; do
  unresolved="$("${runtime_env[@]}" ldd "$executable" 2>/dev/null | awk '/not found/ {print $1}' | sort -u || true)"
  missing+="${unresolved:+$unresolved$'\n'}"
done
missing="$(printf '%s' "$missing" | sed '/^$/d' | sort -u)"
if [[ -n "$missing" ]]; then
  echo "QEMU has unresolved shared libraries: $missing" >&2
  echo "Download those Ubuntu package dependencies into $DEBS and extract them under $PREFIX." >&2
  exit 3
fi
"${runtime_env[@]}" QEMU_DATA_DIR="$PREFIX/usr/share/qemu" "$PREFIX/usr/bin/qemu-system-x86_64" --version | head -1
"${runtime_env[@]}" "$PREFIX/usr/bin/qemu-img" --version | head -1
echo "private prefix: $PREFIX"
echo "No system package install was performed."
