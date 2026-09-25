FROM ubuntu:22.04@sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.10.6-1~22.04.1 \
    python3-tk=3.10.8-1~22.04 \
    xvfb=2:21.1.4-2ubuntu1.7~22.04.16 \
    xdotool=1:3.20160805.1-4 \
    x11-utils=7.7+5build2 \
    x11-apps=7.7+8build2 \
    ca-certificates=20260601~22.04.1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY env/gui_workspace.py /opt/swcub/gui_workspace.py
COPY env/cli_append.py /opt/swcub/cli_append.py
WORKDIR /workspace
CMD ["sleep", "infinity"]
