FROM paragui/professional-rootless:20261103
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    inkscape libreoffice-writer libreoffice-gtk3 python3-uno \
    librsvg2-bin imagemagick ghostscript libxml2-utils \
    tesseract-ocr fonts-inter fonts-liberation fonts-dejavu \
    python3-docx python3-lxml python3-cairosvg python3-pip \
    python3-skimage python3-yaml python3-pdfminer \
    poppler-utils unzip zip nodejs npm dbus-x11 \
    && npm install -g svgo@3.3.2 \
    && pip3 install --break-system-packages --no-cache-dir pytesseract==0.3.13 ImageHash==4.3.2 \
    && fc-cache -f && dpkg-query -W > /opt/weavebench-packages.tsv \
    && npm list -g --depth=0 > /opt/weavebench-npm.txt \
    && rm -rf /var/lib/apt/lists/* /root/.npm
RUN apt-get update && apt-get install -y --no-install-recommends wmctrl \
    && dpkg-query -W > /opt/weavebench-packages.tsv && rm -rf /var/lib/apt/lists/*
