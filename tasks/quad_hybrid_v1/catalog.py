"""Catalog metadata for the 4 four-agent concurrent Hybrid GUI+CLI tasks (QH-01..QH-04)."""
from __future__ import annotations


QUAD_ROLES = ("B", "C", "D", "A")

QUAD_HYBRID_CATALOG = [
    {
        "id": "QH-01",
        "category": "product_launch_4agent",
        "software": "Blender 3.4 + GIMP 2.10 + Inkscape 1.2 + LibreOffice Calc + Chromium Launch Studio",
        "canonical_project": "hero_device.blend",
        "portal_port": 19021,
        "seq_role_timeout_s": 540,
        "conc_role_timeout_s": 780,
        "title": "4-agent product launch studio: visual canvas brief + 3D hero ECO + GIMP/SVG packaging + Calc margin + QA lock",
    },
    {
        "id": "QH-02",
        "category": "smart_grid_4agent",
        "software": "QGIS 3.22 + SpatiaLite + Graphviz + LibreOffice Calc/Writer + Chromium Grid Ops Console",
        "canonical_project": "metro_grid.qgz",
        "portal_port": 19022,
        "seq_role_timeout_s": 540,
        "conc_role_timeout_s": 780,
        "title": "4-agent emergency grid dispatch: visual storm radar canvas + PyQGIS breaker isolation + DAG tie-line + tariff + dispatch PDF",
    },
    {
        "id": "QH-03",
        "category": "robotics_plm_4agent",
        "software": "FreeCAD 0.20 + Blender 3.4 + Inkscape 1.2 + Chromium PLM Blueprint Console",
        "canonical_project": "workcell_assy.FCStd",
        "portal_port": 19023,
        "seq_role_timeout_s": 540,
        "conc_role_timeout_s": 780,
        "title": "4-agent robotics workcell PLM: visual blueprint canvas + FreeCAD base bore ECO + mating mount + SVG panel + Blender twin",
    },
    {
        "id": "QH-04",
        "category": "broadcast_mcr_4agent",
        "software": "MLT melt + FFmpeg + SoX + GIMP 2.10 + LibreOffice Calc + Chromium MCR Switcher",
        "canonical_project": "live_show.mlt",
        "portal_port": 19024,
        "seq_role_timeout_s": 540,
        "conc_role_timeout_s": 780,
        "title": "4-agent live broadcast MCR: visual rundown canvas + FFmpeg/MLT conform + GIMP lower-third + SoX EBU mix + On-Air master",
    },
]

QH_BY_ID = {entry["id"]: entry for entry in QUAD_HYBRID_CATALOG}
