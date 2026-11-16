"""Independent input-derived numerical expectations; never mounted for agents."""
import csv
import heapq
import json
import math
from pathlib import Path


def population_at(records, cutoff):
    selected = {}
    for record in records:
        try:
            count = int(record["residents"])
        except (ValueError, TypeError):
            continue
        if record["quality"] != "approved" or count < 0 or record["observed_at"] > cutoff:
            continue
        identifier = record["parcel_id"]
        if identifier not in selected or record["observed_at"] > selected[identifier]["observed_at"]:
            selected[identifier] = dict(record, residents=count)
    return selected


def risk_class(coverage, population, mean_depth, affected):
    if coverage < .8 or population is None:
        return "Unknown"
    if mean_depth >= 1 or affected >= 100:
        return "High"
    return "Medium" if mean_depth >= .25 or affected >= 20 else "Low"


def shortest_routes(edges, start, wheelchair=False):
    adjacency = {}
    for edge in edges:
        if edge["closed"] or (wheelchair and not edge["accessible"]):
            continue
        adjacency.setdefault(edge["source"], []).append(edge)
    distances, paths = {start: 0.0}, {start: []}
    queue = [(0.0, start)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        for edge in adjacency.get(node, []):
            updated = distance + edge["seconds"] / 60
            target = edge["target"]
            if updated < distances.get(target, float("inf")):
                distances[target] = updated
                paths[target] = paths[node] + [edge["edge_id"]]
                heapq.heappush(queue, (updated, target))
    return distances, paths


def access_oracle(network):
    import numpy as np
    from scipy.optimize import linprog
    choices = []
    for origin in network["origins"]:
        distances, paths = shortest_routes(network["edges"], origin["node"], origin["wheelchair"])
        for shelter in network["shelters"]:
            if shelter["node"] in distances and (not origin["wheelchair"] or shelter["accessible"]):
                choices.append({"origin_id": origin["origin_id"], "shelter_id": shelter["shelter_id"],
                    "minutes": distances[shelter["node"]], "edge_ids": paths[shelter["node"]]})
    constraints, bounds = [], []
    for origin in network["origins"]:
        constraints.append([int(choice["origin_id"] == origin["origin_id"]) for choice in choices])
        bounds.append(origin["demand"])
    for shelter in network["shelters"]:
        constraints.append([int(choice["shelter_id"] == shelter["shelter_id"]) for choice in choices])
        bounds.append(shelter["capacity"])
    maximum = linprog(-np.ones(len(choices)), A_ub=constraints, b_ub=bounds, bounds=(0, None), method="highs")
    if not maximum.success:
        raise RuntimeError(maximum.message)
    served = round(-maximum.fun)
    optimum = linprog([choice["minutes"] for choice in choices], A_ub=constraints, b_ub=bounds,
        A_eq=[np.ones(len(choices))], b_eq=[served], bounds=(0, None), method="highs")
    if not optimum.success or any(abs(value - round(value)) > 1e-6 for value in optimum.x):
        raise RuntimeError("Transportation optimum is not integral")
    allocations = [dict(choice, persons=round(value)) for choice, value in zip(choices, optimum.x) if value > .5]
    return {"served": served, "cost": float(optimum.fun), "allocations": allocations,
            "reachable_origins": sorted({choice["origin_id"] for choice in choices})}


def validate_allocation(rows, network, optimum):
    origins = {entry["origin_id"]: entry for entry in network["origins"]}
    shelters = {entry["shelter_id"]: entry for entry in network["shelters"]}
    edges = {entry["edge_id"]: entry for entry in network["edges"]}
    origin_totals = {identifier: 0 for identifier in origins}
    shelter_totals = {identifier: 0 for identifier in shelters}
    cost, correct_paths = 0.0, True
    try:
        for row in rows:
            origin, shelter = origins[row["origin_id"]], shelters[row["shelter_id"]]
            persons = float(row["persons"])
            if not math.isfinite(persons) or persons <= 0 or persons != int(persons):
                return {"paths": False, "capacity": False, "served": False, "cost": False}
            path = row["edge_ids"]
            path = json.loads(path) if isinstance(path, str) else path
            node, minutes = origin["node"], 0.0
            for identifier in path:
                edge = edges[identifier]
                correct_paths &= edge["source"] == node and not edge["closed"]
                correct_paths &= not origin["wheelchair"] or bool(edge["accessible"])
                node = edge["target"]
                minutes += edge["seconds"] / 60
            correct_paths &= node == shelter["node"] and (not origin["wheelchair"] or shelter["accessible"])
            correct_paths &= math.isclose(float(row["minutes"]), minutes, abs_tol=.001)
            origin_totals[origin["origin_id"]] += int(persons)
            shelter_totals[shelter["shelter_id"]] += int(persons)
            cost += persons * minutes
        capacity = all(origin_totals[key] <= origins[key]["demand"] for key in origins)
        capacity &= all(shelter_totals[key] <= shelters[key]["capacity"] for key in shelters)
        return {"paths": bool(correct_paths), "capacity": bool(capacity),
            "served": sum(origin_totals.values()) == optimum["served"],
            "cost": correct_paths and capacity and cost <= optimum["cost"] * 1.01 + 1e-6,
            "origin_totals": origin_totals, "shelter_totals": shelter_totals, "computed_cost": cost}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {"paths": False, "capacity": False, "served": False, "cost": False}


def exposure_oracle(root):
    import numpy as np
    from osgeo import gdal, ogr, osr
    root = Path(root)
    policy = json.loads((root / "analysis_policy.json").read_text())
    arrays = []
    for source in policy["dem_sources"]:
        warped = gdal.Warp("", str(root / source["file"]), format="MEM", dstSRS="EPSG:32630",
            outputBounds=policy["grid_bounds"], width=80, height=60, resampleAlg="bilinear", dstNodata=-9999)
        values = warped.ReadAsArray().astype(float)
        values[values == -9999] = np.nan
        arrays.append(values * source["metres_per_unit"])
    elevations = np.where(np.isfinite(arrays[1]), arrays[1], arrays[0])
    with (root / "population.csv").open() as stream:
        population = population_at(list(csv.DictReader(stream)), policy["population_cutoff"])
    dataset = ogr.Open(str(root / "review.gpkg"))
    layer = dataset.GetLayerByName("parcels")
    target = osr.SpatialReference()
    target.ImportFromEPSG(32630)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    source_crs = layer.GetSpatialRef().Clone()
    source_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source_crs, target)
    results = []
    west, south, east, north = policy["grid_bounds"]
    for feature in layer:
        geometry = feature.GetGeometryRef().Clone()
        geometry.Transform(transform)
        geometry = geometry.MakeValid()
        identifier = feature.GetField("parcel_id")
        minimum_x, maximum_x, minimum_y, maximum_y = geometry.GetEnvelope()
        valid_area, wet_area, weighted = 0.0, 0.0, 0.0
        for row in range(max(0, int((north - maximum_y) // 10)), min(60, int((north - minimum_y) // 10) + 1)):
            for column in range(max(0, int((minimum_x - west) // 10)), min(80, int((maximum_x - west) // 10) + 1)):
                if not np.isfinite(elevations[row, column]):
                    continue
                left, top = west + column * 10, north - row * 10
                cell = ogr.CreateGeometryFromWkt(f"POLYGON(({left} {top},{left+10} {top},{left+10} {top-10},{left} {top-10},{left} {top}))")
                intersection = geometry.Intersection(cell)
                area = intersection.GetArea() if intersection.GetDimension() == 2 else 0.0
                depth = max(0, feature.GetField("water_m") - elevations[row, column])
                valid_area += area
                weighted += depth * area
                wet_area += area * (depth > .25)
        area = geometry.GetArea()
        coverage = valid_area / area
        residents = population.get(identifier, {}).get("residents")
        mean_depth = weighted / valid_area if valid_area else 0.0
        affected = residents * wet_area / valid_area if residents is not None and valid_area else None
        results.append({"parcel_id": identifier, "area_m2": area, "coverage": coverage,
            "residents": residents, "mean_depth": mean_depth, "wet_area": wet_area, "affected": affected,
            "risk": risk_class(coverage, residents, mean_depth, affected or 0),
            "unknown_reason": ",".join(reason for reason, present in (("coverage", coverage < .8), ("population", residents is None)) if present),
            "geometry_wkt": geometry.ExportToWkt()})
    return sorted(results, key=lambda entry: entry["parcel_id"])
