"""Native p10 authoring and isolated artifact grading; not an agent-visible tool."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from osgeo import gdal, osr
import numpy as np

from tasks.professional_v3.p10_oracle import access_oracle, exposure_oracle, validate_allocation


APP = QgsApplication([], False)
APP.initQgis()
PROJECT = QgsProject.instance()
BASE_LAYERS = ("parcels", "roads", "origins", "shelters")
EXPOSURE_FIELDS = ["parcel_id", "area_m2", "coverage", "residents", "mean_depth", "wet_area", "affected", "risk", "unknown_reason"]
ROUTE_FIELDS = ["origin_id", "shelter_id", "persons", "minutes", "edge_ids"]


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def new_layer(kind, name, fields, crs="EPSG:32630"):
    layer = QgsVectorLayer(f"{kind}?crs={crs}", name, "memory")
    layer.dataProvider().addAttributes([QgsField(field, field_type) for field, field_type in fields])
    layer.updateFields()
    return layer


def add_feature(layer, values, geometry):
    feature = QgsFeature(layer.fields())
    feature.setAttributes(values)
    feature.setGeometry(geometry)
    if not layer.dataProvider().addFeatures([feature])[0]:
        raise RuntimeError("Could not add feature")


def write_layer(layer, file, name, first=False):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = name
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile if first or not Path(file).exists() else QgsVectorFileWriter.CreateOrOverwriteLayer
    error, message, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(file), PROJECT.transformContext(), options)
    if error:
        raise RuntimeError(message)
    result = QgsVectorLayer(str(file) + "|layername=" + name, name, "ogr")
    if not result.isValid():
        raise RuntimeError("Invalid saved layer: " + name)
    return result


def add_to_group(layer, group):
    PROJECT.addMapLayer(layer, False)
    group.addLayer(layer)


def build(root, seed):
    root.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    PROJECT.clear()
    PROJECT.setCrs(QgsCoordinateReferenceSystem("EPSG:32630"))
    PROJECT.setFileName(str(root / "RivertonReview.qgz"))
    PROJECT.writeEntry("Paths", "Absolute", False)
    base = PROJECT.layerTreeRoot().addGroup("Supplied inputs")
    PROJECT.layerTreeRoot().addGroup("Exposure_Review")
    PROJECT.layerTreeRoot().addGroup("Access_Review")
    parcels = new_layer("MultiPolygon", "parcels", [("parcel_id", QVariant.String), ("water_m", QVariant.Double)], "EPSG:4326")
    transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:32630"), parcels.crs(), PROJECT)
    populations = []
    for index in range(36):
        column, row = index % 6, index // 6
        left, bottom = 500013 + column * 112, 5100023 + row * 84
        if index == 5:
            geometry = QgsGeometry.fromWkt(f"POLYGON(({left} {bottom},{left+103} {bottom+73},{left} {bottom+73},{left+103} {bottom},{left} {bottom}))")
        else:
            geometry = QgsGeometry.fromRect(QgsRectangle(left, bottom, left + 103, bottom + 73))
        geometry.transform(transform)
        geometry.convertToMultiType()
        identifier = f"P{index:02d}"
        add_feature(parcels, [identifier, 12.5 + row * .16], geometry)
        if index != 7:
            populations.extend([{"parcel_id": identifier, "residents": 80 + rng.randrange(350), "observed_at": date,
                "quality": "rejected" if index == 9 else quality} for date, quality in
                [("2023-01-01", "approved"), ("2024-12-01", "approved"), ("2024-12-15", "rejected"), ("2026-01-01", "approved")]])
    saved = write_layer(parcels, root / "review.gpkg", "parcels", True)
    saved.renderer().setSymbol(QgsFillSymbol.createSimple({"color": "214,222,225,255", "outline_color": "80,90,110,255"}))
    add_to_group(saved, base)
    with (root / "population.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=["parcel_id", "residents", "observed_at", "quality"])
        writer.writeheader()
        writer.writerows(populations)
    projection = osr.SpatialReference()
    projection.ImportFromEPSG(32630)
    for name, left, factor, bias in (("west", 500000, 1, 0), ("east", 500300, .3048, .13)):
        values = np.zeros((60, 50), dtype=np.float32)
        for row in range(60):
            for column in range(50):
                coordinate_x, coordinate_y = left + column * 10 + 5, 5100600 - row * 10 - 5
                value = 10 + (coordinate_x - 500000) * .006 + (coordinate_y - 5100000) * .0008 + .28 * math.sin(column / 7) + bias
                values[row, column] = value / factor
                if coordinate_x < 500120 and coordinate_y < 5100120:
                    values[row, column] = -9999
        temporary = root / (name + "_utm.tif")
        raster = gdal.GetDriverByName("GTiff").Create(str(temporary), 50, 60, 1, gdal.GDT_Float32)
        raster.SetGeoTransform([left, 10, 0, 5100600, 0, -10])
        raster.SetProjection(projection.ExportToWkt())
        raster.GetRasterBand(1).SetNoDataValue(-9999)
        raster.GetRasterBand(1).WriteArray(values)
        raster = None
        target = root / (name + "_dem.tif")
        if name == "east":
            gdal.Warp(str(target), str(temporary), dstSRS="EPSG:3857", resampleAlg="bilinear", dstNodata=-9999)
            temporary.unlink()
        else:
            temporary.rename(target)
        raster_layer = QgsRasterLayer(str(target), name + " DEM")
        add_to_group(raster_layer, base)
        base.findLayer(raster_layer.id()).setItemVisibilityChecked(False)
    nodes = {str(index): [500025 + index % 7 * 105, 5100060 + index // 7 * 110] for index in range(35)}
    nodes["35"] = [500760, 5100430]
    edges = []
    def edge(source, target, closed=False):
        index = len(edges)
        edges.append({"edge_id": f"E{index:03d}", "source": str(source), "target": str(target),
                      "seconds": 55 + index % 17 * 3, "closed": bool(closed or index % 23 == 9), "accessible": index % 13 != 7})
    for node in range(35):
        if node % 7 < 6:
            edge(node, node + 1)
            if node % 3 != 1:
                edge(node + 1, node)
        if node < 28:
            edge(node, node + 7)
            edge(node + 7, node)
    edge(35, 34, True)
    edge(34, 35, True)
    origins = [{"origin_id": f"O{index:02d}", "node": str(node), "demand": 12 + index % 4 * 7, "wheelchair": index % 3 == 1}
               for index, node in enumerate([0, 2, 8, 10, 14, 16, 18, 22, 24, 29, 32, 35])]
    shelters = [{"shelter_id": f"S{index}", "node": str(node), "capacity": capacity, "accessible": index != 1}
                for index, (node, capacity) in enumerate([(6, 50), (28, 45), (34, 40)])]
    network = {"nodes": nodes, "edges": edges, "origins": origins, "shelters": shelters}
    save_json(root / "network.json", network)
    roads = new_layer("LineString", "roads", [("edge_id", QVariant.String), ("closed", QVariant.Int)])
    for record in edges:
        geometry = QgsGeometry.fromPolylineXY([QgsPointXY(*nodes[record[key]]) for key in ("source", "target")])
        add_feature(roads, [record["edge_id"], int(record["closed"])], geometry)
    roads = write_layer(roads, root / "review.gpkg", "roads")
    roads.renderer().setSymbol(QgsLineSymbol.createSimple({"line_color": "100,105,110", "line_width": ".4"}))
    add_to_group(roads, base)
    for name, records, field in (("origins", origins, "origin_id"), ("shelters", shelters, "shelter_id")):
        layer = new_layer("Point", name, [(field, QVariant.String)])
        for record in records:
            add_feature(layer, [record[field]], QgsGeometry.fromPointXY(QgsPointXY(*nodes[record["node"]])))
        saved = write_layer(layer, root / "review.gpkg", name)
        saved.renderer().setSymbol(QgsMarkerSymbol.createSimple({"name": "circle" if name == "origins" else "square", "color": "40,65,170" if name == "origins" else "30,140,60", "size": "3"}))
        add_to_group(saved, base)
    policy = {"review_date": "2025-01-01", "population_cutoff": "2025-01-01", "grid_bounds": [500000, 5100000, 500800, 5100600],
        "grid_resolution_m": 10, "width": 80, "height": 60, "crs": "EPSG:32630", "resampling": "bilinear",
        "nodata": "Ignore invalid cells; sample east if valid, otherwise west; never extrapolate missing coverage",
        "overlap_priority": ["east", "west"], "vertical_datum": "common synthetic local datum",
        "dem_sources": [{"file": "west_dem.tif", "horizontal_crs": "EPSG:32630", "metres_per_unit": 1},
                        {"file": "east_dem.tif", "horizontal_crs": "EPSG:3857", "metres_per_unit": .3048}],
        "repair": "MakeValid, retaining all polygon pieces under the original parcel_id; source tables are immutable",
        "fields": EXPOSURE_FIELDS, "derived_table": "exposure_parcels", "numeric_tolerance": "max(0.005, abs(expected)*1e-5)",
        "quality_summary": "exposure_summary.csv has one row per derived parcel, with the same named fields; counts/quality/source-date summary also appears in the native layout",
        "coverage": "valid cell-intersection area / repaired parcel area; classification uses unrounded values",
        "missing_population": "NULL residents and affected; never zero; ignore rejected, future and negative observations",
        "unknown_reason_codes": ["coverage", "population"], "mean_depth_without_coverage": 0}
    save_json(root / "analysis_policy.json", policy)
    save_json(root / "access_policy.json", {"review_date": "2025-01-01", "source": "network.json", "crs": "EPSG:32630",
        "travel_cost": "seconds/60 per directed admissible edge; linear person-minutes", "allocation_fields": ROUTE_FIELDS,
        "derived_route_table": "access_routes", "exception_table": "access_exceptions",
        "exception_fields": ["origin_id", "demand", "served", "unserved", "reason"],
        "exception_codes": ["unreachable", "capacity", "served"], "exception_scope": "exactly one record per origin",
        "allocation_csv": "positive allocation rows only, same fields as access_routes; edge_ids is an ordered JSON array",
        "objective": "maximize served persons, then minimize cost; integer persons; routes may split origins; 1% cost tolerance",
        "inputs_immutable": True, "road_closure_display": "show closed roads distinctly in the role layout without modifying the supplied layer's renderer"})
    PROJECT.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(QgsRectangle(499980, 5099980, 500820, 5100620), PROJECT.crs()))
    if not PROJECT.write():
        raise RuntimeError("Project write failed")


def values(layer):
    result = []
    for feature in layer.getFeatures():
        record = {field.name(): (None if feature[field.name()] == NULL else feature[field.name()]) for field in layer.fields()}
        record["geometry_wkt"] = feature.geometry().asWkt(8)
        result.append(record)
    return result


def baseline_state(root):
    return {name: values(QgsVectorLayer(str(root / "review.gpkg") + "|layername=" + name, name, "ogr")) for name in BASE_LAYERS}


def csv_write(file, fields, records):
    with file.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, list) else value for key, value in record.items()} for record in records)


def layout_create(name, layers, text, file):
    old = PROJECT.layoutManager().layoutByName(name)
    if old:
        PROJECT.layoutManager().removeLayout(old)
    layout = QgsPrintLayout(PROJECT)
    layout.initializeDefaults()
    layout.setName(name)
    layout.pageCollection().pages()[0].setPageSize("A4", QgsLayoutItemPage.Landscape)
    title = QgsLayoutItemLabel(layout)
    title.setText(name.replace("_", " ") + " — Riverton / 2025-01-01")
    title.attemptMove(QgsLayoutPoint(10, 5))
    title.attemptResize(QgsLayoutSize(270, 15))
    layout.addLayoutItem(title)
    map_item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(10, 25))
    map_item.attemptResize(QgsLayoutSize(195, 155))
    map_item.setLayers(layers)
    map_item.setKeepLayerSet(True)
    map_item.setCrs(PROJECT.crs())
    map_item.setExtent(QgsRectangle(499980, 5099980, 500820, 5100620))
    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.setAutoUpdateModel(False)
    legend.model().rootGroup().clear()
    for layer in layers:
        legend.model().rootGroup().addLayer(layer)
    legend.attemptMove(QgsLayoutPoint(212, 25))
    layout.addLayoutItem(legend)
    note = QgsLayoutItemLabel(layout)
    note.setText(text)
    note.attemptMove(QgsLayoutPoint(212, 88))
    note.attemptResize(QgsLayoutSize(76, 105))
    layout.addLayoutItem(note)
    scale = QgsLayoutItemScaleBar(layout)
    scale.setStyle("Single Box")
    scale.setLinkedMap(map_item)
    scale.setUnits(QgsUnitTypes.DistanceMeters)
    scale.setUnitsPerSegment(100)
    scale.setNumberOfSegments(3)
    scale.setNumberOfSegmentsLeft(0)
    scale.setUnitLabel("m")
    scale.applyDefaultSize()
    scale.attemptMove(QgsLayoutPoint(12, 185))
    layout.addLayoutItem(scale)
    PROJECT.layoutManager().addLayout(layout)
    if QgsLayoutExporter(layout).exportToPdf(str(file), QgsLayoutExporter.PdfExportSettings()) != QgsLayoutExporter.Success:
        raise RuntimeError("PDF export failed")


def reference(root, expected, role):
    PROJECT.clear()
    assert PROJECT.read(str(root / "RivertonReview.qgz"))
    name = "Exposure_Review" if role == "a" else "Access_Review"
    prefix = "exposure" if role == "a" else "access"
    directory = root / "exports" / prefix
    directory.mkdir(parents=True, exist_ok=True)
    group = PROJECT.layerTreeRoot().findGroup(name)
    for layer in list(PROJECT.mapLayers().values()):
        if layer.name().startswith(prefix + "_"):
            PROJECT.removeMapLayer(layer)
    if role == "a":
        fields = [(field, QVariant.String if field in ("parcel_id", "risk", "unknown_reason") else QVariant.Double) for field in EXPOSURE_FIELDS]
        layer = new_layer("MultiPolygon", "exposure_parcels", fields)
        for record in expected["exposure"]:
            geometry = QgsGeometry.fromWkt(record["geometry_wkt"])
            geometry.convertToMultiType()
            add_feature(layer, [record[field] for field in EXPOSURE_FIELDS], geometry)
        layer = write_layer(layer, root / "review.gpkg", "exposure_parcels")
        layer.setRenderer(QgsCategorizedSymbolRenderer("risk", [QgsRendererCategory(label,
            QgsFillSymbol.createSimple({"color": color}), label) for label, color in
            (("Low", "#c5e4bd"), ("Medium", "#f6bd49"), ("High", "#be343b"), ("Unknown", "#969696"))]))
        add_to_group(layer, group)
        write_layer(layer, directory / "exposure_release.gpkg", "exposure_parcels", True)
        csv_write(directory / "exposure_summary.csv", EXPOSURE_FIELDS, expected["exposure"])
        counts = Counter(record["risk"] for record in expected["exposure"])
        text = "Quality / valid coverage\n" + "\n".join(f"{key}: {value}" for key, value in sorted(counts.items()))
        text += "\n\nNoData preserved\nUnits: metres\nPopulation cutoff:\n2025-01-01\nSynthetic review only"
        layout_create(name, [layer], text, directory / "exposure_review.pdf")
    else:
        network = expected["network"]
        edges = {edge["edge_id"]: edge for edge in network["edges"]}
        layer = new_layer("LineString", "access_routes", [(field, QVariant.String if field in ("origin_id", "shelter_id", "edge_ids") else QVariant.Double) for field in ROUTE_FIELDS])
        for record in expected["access"]["allocations"]:
            path = record["edge_ids"]
            coordinates = [network["nodes"][edges[path[0]]["source"]]] + [network["nodes"][edges[identifier]["target"]] for identifier in path]
            add_feature(layer, [json.dumps(record[field]) if field == "edge_ids" else record[field] for field in ROUTE_FIELDS],
                        QgsGeometry.fromPolylineXY([QgsPointXY(*point) for point in coordinates]))
        layer = write_layer(layer, root / "review.gpkg", "access_routes")
        layer.renderer().setSymbol(QgsLineSymbol.createSimple({"line_color": "30,80,180", "line_width": "1"}))
        add_to_group(layer, group)
        exceptions = new_layer("Point", "access_exceptions", [(field, QVariant.String if field in ("origin_id", "reason") else QVariant.Int) for field in ("origin_id", "demand", "served", "unserved", "reason")])
        totals = Counter()
        for row in expected["access"]["allocations"]:
            totals[row["origin_id"]] += row["persons"]
        for origin in network["origins"]:
            served = totals[origin["origin_id"]]
            reason = "unreachable" if origin["origin_id"] not in expected["access"]["reachable_origins"] else "capacity" if served < origin["demand"] else "served"
            add_feature(exceptions, [origin["origin_id"], origin["demand"], served, origin["demand"] - served, reason],
                        QgsGeometry.fromPointXY(QgsPointXY(*network["nodes"][origin["node"]])))
        exceptions = write_layer(exceptions, root / "review.gpkg", "access_exceptions")
        exceptions.setRenderer(QgsCategorizedSymbolRenderer("reason", [QgsRendererCategory(label, QgsMarkerSymbol.createSimple({"name": "circle", "color": color, "size": "3"}), label)
            for label, color in (("served", "#25a35b"), ("capacity", "#f1a02a"), ("unreachable", "#b72c35"))]))
        add_to_group(exceptions, group)
        closures = new_layer("LineString", "access_closures", [])
        for edge in network["edges"]:
            if edge["closed"]:
                add_feature(closures, [], QgsGeometry.fromPolylineXY([QgsPointXY(*network["nodes"][edge[key]]) for key in ("source", "target")]))
        closures = write_layer(closures, root / "review.gpkg", "access_closures")
        closures.renderer().setSymbol(QgsLineSymbol.createSimple({"line_color": "190,30,40", "line_width": ".9", "line_style": "dash"}))
        add_to_group(closures, group)
        for index, output in enumerate((layer, exceptions, closures)):
            write_layer(output, directory / "access_routes.gpkg", output.name(), index == 0)
        csv_write(directory / "allocation.csv", ROUTE_FIELDS, expected["access"]["allocations"])
        text = f"Allocation review\nDemand: {sum(origin['demand'] for origin in network['origins'])}\nServed: {expected['access']['served']}\nUnserved: {sum(origin['demand'] for origin in network['origins'])-expected['access']['served']}\nCost: {expected['access']['cost']:.2f}\nperson-minutes\n\nRed dashed: closed\n2025-01-01\nSynthetic exercise"
        layout_create(name, [exceptions, closures, layer, PROJECT.mapLayersByName("roads")[0]], text, directory / "access_review.pdf")
    assert PROJECT.write()


def equivalent_number(actual, expected):
    if expected is None:
        return actual is None or actual == ""
    try:
        value = float(actual)
        return math.isfinite(value) and abs(value - expected) <= max(.005, abs(expected) * 1e-5)
    except (ValueError, TypeError):
        return False


def table_records(file, name):
    layer = QgsVectorLayer(str(file) + "|layername=" + name, name, "ogr")
    return values(layer) if layer.isValid() else []


def compare_exposure(records, expected, fields):
    keyed = {record.get("parcel_id"): record for record in records}
    if len(keyed) != len(records) or set(keyed) != {record["parcel_id"] for record in expected}:
        return False
    for target in expected:
        record = keyed[target["parcel_id"]]
        for field in fields:
            if field in ("risk", "unknown_reason"):
                if set(str(record.get(field) or "").split(",")) != set(target[field].split(",")):
                    return False
            elif not equivalent_number(record.get(field), target[field]):
                return False
    return True


def pdf_matches(layout, file, temporary):
    if not layout or not file.is_file():
        return False
    from PIL import Image, ImageChops, ImageStat
    expected_file = temporary / (layout.name() + ".pdf")
    if QgsLayoutExporter(layout).exportToPdf(str(expected_file), QgsLayoutExporter.PdfExportSettings()) != QgsLayoutExporter.Success:
        return False
    images = []
    for index, path in enumerate((file, expected_file)):
        prefix = temporary / (layout.name() + str(index))
        subprocess.run(["pdftoppm", "-scale-to", "800", "-singlefile", "-png", str(path), str(prefix)], check=True, capture_output=True, timeout=30)
        images.append(Image.open(str(prefix) + ".png").convert("RGB"))
    return images[0].size == images[1].size and max(ImageStat.Stat(ImageChops.difference(*images)).mean) < 3


def live_checks(observations, expected):
    exposure = expected["exposure"]
    maximum = max((row for row in exposure if row["affected"] is not None), key=lambda row: row["affected"])["parcel_id"]
    low_coverage = {row["parcel_id"] for row in exposure if row["coverage"] < .8}
    totals = Counter()
    for row in expected["access"]["allocations"]:
        totals[row["origin_id"]] += row["persons"]
    partial = {row["origin_id"] for row in expected["network"]["origins"] if 0 < totals[row["origin_id"]] < row["demand"]}
    unreachable = {row["origin_id"] for row in expected["network"]["origins"]} - set(expected["access"]["reachable_origins"])
    roles = {}
    for role in ("a", "b"):
        selected, layouts = set(), set()
        for event in observations:
            state = event.get("state", {})
            if event.get("task") != "p10" + role or not event.get("qgis_window_verified") or not state.get("canvas_visible"):
                continue
            layouts.update(state.get("layouts_visible", []))
            if state.get("table_visible") and state.get("selection_in_canvas"):
                field = "parcel_id" if role == "a" else "origin_id"
                selected.update(str(row[field]) for row in state.get("selected", []) if field in row)
        roles[role] = (maximum in selected and bool(low_coverage & selected) and "Exposure_Review" in layouts) if role == "a" else (
            bool(partial & selected) and bool(unreachable & selected) and "Access_Review" in layouts)
    return roles


def grade(root, trusted, observations, output):
    output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((trusted / "expected.json").read_text())
    checks = {role: {key: False for key in expected["check_ids"][role]} for role in ("a", "b")}
    errors = []
    PROJECT.clear()
    opened = PROJECT.read(str(root / "RivertonReview.qgz"))
    baseline_ok = baseline_state(root) == expected["baseline"]
    immutable_ok = all((root / name).is_file() and hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in expected["immutable_hashes"].items())
    portable = opened and all(layer.isValid() and Path(layer.source().split("|")[0]).resolve().is_relative_to(root.resolve()) for layer in PROJECT.mapLayers().values())
    gate = baseline_ok and immutable_ok and portable
    records = table_records(root / "review.gpkg", "exposure_parcels")
    for index, fields in enumerate((["area_m2", "residents"], ["coverage", "mean_depth"], ["wet_area", "affected"], ["risk", "unknown_reason"])):
        checks["a"][expected["check_ids"]["a"][index]] = compare_exposure(records, expected["exposure"], fields)
    if records:
        expected_geometries = {record["parcel_id"]: QgsGeometry.fromWkt(record["geometry_wkt"]) for record in expected["exposure"]}
        checks["a"][expected["check_ids"]["a"][0]] &= all(QgsGeometry.fromWkt(record["geometry_wkt"]).isGeosValid() and
            QgsGeometry.fromWkt(record["geometry_wkt"]).symDifference(expected_geometries[record["parcel_id"]]).area() < .1 for record in records if record.get("parcel_id") in expected_geometries)
    route_records = table_records(root / "review.gpkg", "access_routes")
    allocation = validate_allocation(route_records, expected["network"], expected["access"])
    for index, key in enumerate(("paths", "capacity", "served", "cost")):
        checks["b"][expected["check_ids"]["b"][index]] = bool(route_records) and allocation[key]
    live = live_checks(observations, expected)
    for role, prefix, layout_name, table_name, export_name, csv_name in (
        ("a", "exposure", "Exposure_Review", "exposure_parcels", "exposure_release.gpkg", "exposure_summary.csv"),
        ("b", "access", "Access_Review", "access_routes", "access_routes.gpkg", "allocation.csv")):
        try:
            layout = PROJECT.layoutManager().layoutByName(layout_name)
            owned = PROJECT.mapLayersByName(table_name)
            maps = [item for item in layout.items() if isinstance(item, QgsLayoutItemMap)] if layout else []
            page = layout.pageCollection().pages()[0].pageSize() if layout else None
            binding = bool(layout and owned and maps and page and abs(page.width() - 297) < 1 and abs(page.height() - 210) < 1)
            binding &= any(any(layer.id() == owned[0].id() for layer in map_item.layers()) for map_item in maps) if owned else False
            binding &= any(isinstance(item, QgsLayoutItemScaleBar) for item in layout.items()) if layout else False
            binding &= any(isinstance(item, QgsLayoutItemLegend) for item in layout.items()) if layout else False
            if role == "a" and owned:
                renderer = owned[0].renderer()
                binding &= isinstance(renderer, QgsCategorizedSymbolRenderer) and renderer.classAttribute() == "risk" and "Unknown" in {category.value() for category in renderer.categories()}
            if role == "b":
                network = expected["network"]
                edge_map = {edge["edge_id"]: edge for edge in network["edges"]}
                for row in route_records:
                    identifiers = json.loads(row["edge_ids"])
                    coordinates = [network["nodes"][edge_map[identifiers[0]]["source"]]] + [network["nodes"][edge_map[identifier]["target"]] for identifier in identifiers]
                    target = QgsGeometry.fromPolylineXY([QgsPointXY(*point) for point in coordinates])
                    binding &= QgsGeometry.fromWkt(row["geometry_wkt"]).hausdorffDistance(target) < .1
            checks[role][expected["check_ids"][role][4]] = bool(binding)
            directory = root / "exports" / prefix
            exports = table_records(directory / export_name, table_name)
            with (directory / csv_name).open() as stream:
                csv_rows = list(csv.DictReader(stream))
            if role == "a":
                exchange = compare_exposure(exports, expected["exposure"], EXPOSURE_FIELDS[1:]) and compare_exposure(csv_rows, expected["exposure"], EXPOSURE_FIELDS[1:])
            else:
                export_validation = validate_allocation(exports, network, expected["access"])
                csv_validation = validate_allocation(csv_rows, network, expected["access"])
                exchange = all(export_validation[key] and csv_validation[key] for key in ("paths", "capacity", "served", "cost"))
                canonical = lambda rows: sorted((row["origin_id"], row["shelter_id"], float(row["persons"]), json.dumps(json.loads(row["edge_ids"]) if isinstance(row["edge_ids"], str) else row["edge_ids"])) for row in rows)
                exchange &= canonical(route_records) == canonical(exports) == canonical(csv_rows)
                exceptions = {row["origin_id"]: row for row in table_records(root / "review.gpkg", "access_exceptions")}
                for origin in network["origins"]:
                    record = exceptions.get(origin["origin_id"], {})
                    served = allocation.get("origin_totals", {}).get(origin["origin_id"], 0)
                    reason = "unreachable" if origin["origin_id"] not in expected["access"]["reachable_origins"] else "capacity" if served < origin["demand"] else "served"
                    exchange &= record.get("demand") == origin["demand"] and record.get("served") == served and record.get("unserved") == origin["demand"] - served and record.get("reason") == reason
            checks[role][expected["check_ids"][role][5]] = bool(exchange and pdf_matches(layout, directory / (prefix + "_review.pdf"), output))
            checks[role][expected["check_ids"][role][6]] = bool(portable and binding) if role == "a" else bool(binding and PROJECT.mapLayersByName("access_exceptions"))
            checks[role][expected["check_ids"][role][7]] = live[role]
        except Exception as error:
            errors.append({"role": role, "error": type(error).__name__ + ": " + str(error)})
    result = {role: {"score": sum(checks[role].values()) / 8 if gate else 0,
        "artifact_score": sum(list(checks[role].values())[:7]) / 7 if gate else 0,
        "success": gate and all(checks[role].values()), "checks": checks[role], "gate": bool(gate)} for role in ("a", "b")}
    result["diagnostics"] = {"opened": opened, "baseline_preserved": baseline_ok, "immutable_preserved": immutable_ok, "portable": portable, "errors": errors}
    save_json(output / "scores.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "reference", "grade"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--trusted", type=Path, required=True)
    parser.add_argument("--role", choices=("a", "b"))
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not Path("/.dockerenv").exists():
        raise RuntimeError("Native authoring/evaluation must run in Docker")
    if args.command == "build":
        build(args.workspace, 1)
        args.trusted.mkdir(parents=True, exist_ok=False)
        catalog = json.loads((Path(__file__).parent / "catalog.json").read_text())
        pair = next(pair for pair in catalog["pairs"] if pair["id"] == "p10")
        expected = {"exposure": exposure_oracle(args.workspace), "network": json.loads((args.workspace / "network.json").read_text()),
            "baseline": baseline_state(args.workspace), "check_ids": {role: pair["agents"][role]["critical_checks"] for role in ("a", "b")},
            "immutable_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in args.workspace.iterdir() if path.suffix in (".json", ".csv", ".tif")}}
        expected["access"] = access_oracle(expected["network"])
        save_json(args.trusted / "expected.json", expected)
        print(json.dumps({"parcels": len(expected["exposure"]), "risk_counts": dict(Counter(row['risk'] for row in expected['exposure'])), "maximum_served": expected["access"]["served"], "optimal_person_minutes": expected["access"]["cost"]}))
    elif args.command == "reference":
        reference(args.workspace, json.loads((args.trusted / "expected.json").read_text()), args.role)
    else:
        observations = [json.loads(line) for line in args.observations.read_text().splitlines()] if args.observations and args.observations.exists() else []
        print(json.dumps(grade(args.workspace, args.trusted, observations, args.out)))


if __name__ == "__main__":
    main()
