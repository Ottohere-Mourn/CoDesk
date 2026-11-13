"""Text/state oracles for EDIT-MODE1; read saved ODT content, not screenshots."""
from __future__ import annotations
import xml.etree.ElementTree as ET
import zipfile
from evaluation_examples.task_class.pg_common import expected, fetch, result

HOME = "/home/user"
DOC = f"{HOME}/Documents/Operations/Release-review.odt"
TEXT_P = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"

def document(env, dest):
    path = fetch(env, DOC, dest + ".odt")
    if not path:
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        return ["".join(node.itertext()) for node in root.iter(TEXT_P)]
    except (ET.ParseError, OSError, KeyError, zipfile.BadZipFile):
        return None

def evaluate_insert(env, dest):
    lines = document(env, dest)
    if lines is None:
        return result(0.0, {"document_readable": False})
    exp = expected("e1")
    checks = {
        "status_inserted_without_overwriting_guard": len(lines) >= 3 and lines[0] == exp["a_line"],
        "reviewer_code_initial_or_correctly_updated": len(lines) >= 3 and lines[1] in (exp["lines"][1], exp["b_line"]),
        "guard_phrase_preserved": len(lines) >= 3 and lines[2] == exp["lines"][2],
        "no_extra_paragraphs": len(lines) == 3,
    }
    return result(sum(checks.values()) / len(checks), checks)

def evaluate_code(env, dest):
    lines = document(env, dest)
    if lines is None:
        return result(0.0, {"document_readable": False})
    exp = expected("e1")
    checks = {
        "fixed_width_code_updated": len(lines) >= 3 and lines[1] == exp["b_line"],
        "status_line_initial_or_correctly_updated": len(lines) >= 3 and lines[0] in (exp["lines"][0], exp["a_line"]),
        "guard_phrase_preserved": len(lines) >= 3 and lines[2] == exp["lines"][2],
        "no_extra_paragraphs": len(lines) == 3,
    }
    return result(sum(checks.values()) / len(checks), checks)
