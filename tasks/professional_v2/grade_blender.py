"""Semantic p4 scoring from a fresh native inspector and a trusted seed snapshot."""

import math


def close(actual, expected, tolerance=0.002):
    return isinstance(actual, (float, int)) and math.isfinite(actual) and abs(actual - expected) <= tolerance


def vector(actual, expected, tolerance=0.002):
    return isinstance(actual, list) and len(actual) == len(expected) and all(
        close(value, target, tolerance) for value, target in zip(actual, expected))


def target_color(channels):
    return [channel / 255 / 12.92 if channel / 255 <= 0.04045
            else ((channel / 255 + 0.055) / 1.055) ** 2.4 for channel in channels] + [1.0]


def grade(state, baseline):
    invariants = state.get("invariants", {})
    expected = baseline["invariants"]
    gates = {
        "native_reopened": state.get("native_reopened") is True,
        "no_external_dependencies": state.get("external_dependencies") == [],
        "scene_and_unowned_state_preserved": invariants == expected,
    }
    curves = state.get("motion", {}).get("curves", [])
    samples = state.get("motion", {}).get("samples", {})
    keys = curves[0].get("keys", []) if len(curves) == 1 else []
    editable = (len(curves) == 1 and curves[0].get("path") == "rotation_euler"
                and curves[0].get("index") == 0 and curves[0].get("modifiers") == 0
                and curves[0].get("muted") is False
                and len(keys) == 3 and vector([key.get("frame") for key in keys], [1, 31, 61]))
    poses = all(vector(samples.get(str(frame)), [math.radians(angle), 0, 0])
                for frame, angle in ((1, 0), (31, -60), (61, 0)))
    linear = (editable and all(key.get("interpolation") == "LINEAR" for key in keys)
              and all(vector(samples.get(str(frame)), [-math.pi / 6, 0, 0]) for frame in (16, 46)))
    objects = invariants.get("objects", {})
    materials = state.get("materials", {})
    shell = materials.get("ShellFinish", {})
    dial = materials.get("DialFinish", {})
    shell_values, dial_values = shell.get("values", {}), dial.get("values", {})
    checks = {
        "a": {
            "editable_rotation_keys": editable,
            "three_key_poses": poses,
            "linear_midpoint_motion": linear,
            "hinge_geometry_preserved": objects.get("CaseLid") == expected["objects"]["CaseLid"],
            "scene_preserved": gates["scene_and_unowned_state_preserved"],
            "native_reopened": gates["native_reopened"] and gates["no_external_dependencies"],
        },
        "b": {
            "shell_color": vector(shell_values.get("Base Color"), target_color((24, 91, 122))),
            "shell_surface": close(shell_values.get("Roughness"), 0.32) and close(shell_values.get("Metallic"), 0.15),
            "dial_color": vector(dial_values.get("Base Color"), target_color((230, 183, 74))),
            "dial_surface": close(dial_values.get("Roughness"), 0.22) and close(dial_values.get("Metallic"), 0.80),
            "connected_material_slots": shell.get("connected") is True and dial.get("connected") is True
                and objects.get("ShellBody", {}).get("materials") == ["ShellFinish"]
                and objects.get("ControlDial", {}).get("materials") == ["DialFinish"],
            "assets_preserved": gates["scene_and_unowned_state_preserved"],
        },
    }
    result = {"gates": gates, "gate_passed": all(gates.values()), "roles": {}}
    for role, role_checks in checks.items():
        passed = sum(bool(value) for value in role_checks.values())
        result["roles"][role] = {
            "checks": role_checks, "passed": passed, "total": len(role_checks),
            "raw_score": passed / len(role_checks),
            "score": passed / len(role_checks) if result["gate_passed"] else 0.0,
        }
    return result
