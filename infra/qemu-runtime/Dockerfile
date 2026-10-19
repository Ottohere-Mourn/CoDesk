# QEMU runtime for the OSWorld-V2 Ubuntu Guest that also works without /dev/kvm (TCG software emulation).
# Drop-in for the upstream provider image: same ports, the Guest qcow2 is mounted read-only at /System.qcow2.
FROM ubuntu:22.04@sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends qemu-system-x86 qemu-utils ovmf \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/oscombo-qemu-entrypoint
RUN chmod 0755 /usr/local/bin/oscombo-qemu-entrypoint

EXPOSE 5000 8006 8080 9222
ENTRYPOINT ["/usr/local/bin/oscombo-qemu-entrypoint"]
