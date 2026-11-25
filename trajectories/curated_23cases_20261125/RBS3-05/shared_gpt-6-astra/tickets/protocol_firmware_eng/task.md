# CAN-FD Gateway Firmware Remediation & ASIC Power Envelope Work Order — `protocol_firmware_eng`

## Scope & Deliverables
Remediate the live `:19515` CAN-FD daemon in `/workspace/gateway/gateway_daemon.py` and finalize the ASIC IO rail budget in `/workspace/gateway/Board_Thermal_BOM.xlsx` (open in LibreOffice Calc with active desk tag in `VRM_Zones!C1`), using the **Hardware Compliance Portal** at `http://127.0.0.1:19505/`.

Deliverables:
1. Under `MODE = CAN_FD_VECTOR_SPEC` in the open Chromium portal, export `/home/user/Downloads/board_compliance.csv` and copy the CAN Protocol Seal to the clipboard.
2. Fix `/workspace/gateway/gateway_daemon.py` so `POST http://127.0.0.1:19515/api/frame` enforces `CRC-16/CCITT-FALSE` (`poly=0x1021, init=0xFFFF`) and rejects `burst_index > 8` with `accepted=false, status='RATE_LIMITED'`, and restart the live daemon on `127.0.0.1:19515` (preserving `GET /status`).
3. Sum `load_w` across `enabled=1` rails from `CAN_FD_VECTOR_SPEC` into `Power_Envelope!B3` (`ASIC_Enabled_IO_W`), set `Power_Envelope!B8` to the CAN Protocol Seal, size `Protocol_Guardband_B_W` (`B5` in `[0.5, 6.0]`) so `Power_Envelope!B6` (`=SUM(B2:B5)`) lands in `[190.0, 190.8]` W (preserving `VRM_Zones!C1` and `B2, B4, B7`), export `/workspace/gateway/Protocol_Compliance.pdf`, and write `/workspace/gateway/FIRMWARE_SUMMARY.json` (`asic_enabled_io_w`, `can_seal`).
