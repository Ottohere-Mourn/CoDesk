# BC-01–BC-04 Guest Dependency Probe

Date: 2026-11-26

The check used a disposable OSWorld Guest container with a separate qcow overlay under the RAID run area, loopback-only temporary host ports, and the base qcow mounted read-only. The probe commands only queried executable lookup and Python import availability.

The Guest, Docker container, SSH tunnel, and RAID temporary directory were removed immediately after the probe. A post-cleanup check showed no matching container, no temporary probe directory, and no listeners on the probe ports. The C01–C24 queue and its containers were not touched.

| Dependency | Result | Guest path / detail |
|---|---|---|
| Chromium binary | Not found under chromium / chromium-browser | — |
| Google Chrome | Present | /usr/bin/google-chrome, /usr/bin/google-chrome-stable |
| LibreOffice / Calc | Present | /usr/bin/libreoffice, /usr/bin/soffice |
| Inkscape | **Missing** | — |
| GIMP | Present | /usr/bin/gimp |
| Git | Present | /usr/bin/git |
| VS Code | Present | /usr/bin/code |
| Python | Present | 3.10.12 |
| openpyxl | Missing | import openpyxl unavailable |
| PyYAML | Present | import yaml available |
| sqlite3 module / CLI | Module present | Python sqlite3; SQLite library 3.37.2 |
| Pillow | Present | import PIL available |
| pdftotext | Present | /usr/bin/pdftotext |
| pypdf | Missing | — |
| pdfplumber | Missing | — |
| PyMuPDF (fitz) | Missing | — |

Because Inkscape is absent, this implementation pass is limited to BC-01–BC-03. BC-04 remains unimplemented pending the requested replacement-tool decision. BC-02 uses a standard-library OOXML generator/parser for starter workbooks; its PDF path uses the already-present pdftotext at Guest/host evaluation time, with injectable text extraction for offline tests.
