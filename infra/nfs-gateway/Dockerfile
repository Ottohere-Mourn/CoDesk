FROM ubuntu:22.04@sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
      sed -i 's/Components: main/Components: main universe/' /etc/apt/sources.list.d/ubuntu.sources; \
    else \
      printf '%s\n' \
        'deb http://archive.ubuntu.com/ubuntu jammy main universe' \
        'deb http://archive.ubuntu.com/ubuntu jammy-updates main universe' \
        'deb http://security.ubuntu.com/ubuntu jammy-security main universe' \
        > /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nfs-ganesha=3.5-1ubuntu1 nfs-ganesha-vfs=3.5-1ubuntu1; \
    dpkg-query -W -f='${Package}=${Version}\n' nfs-ganesha nfs-ganesha-vfs > /usr/share/codesk-nfs-packages.txt; \
    rm -rf /var/lib/apt/lists/*
COPY ganesha.conf.template /etc/ganesha/ganesha.conf.template
COPY entrypoint.sh /usr/local/bin/codesk-nfs-entrypoint
RUN chmod 0755 /usr/local/bin/codesk-nfs-entrypoint
EXPOSE 12049/tcp
ENTRYPOINT ["/usr/local/bin/codesk-nfs-entrypoint"]
