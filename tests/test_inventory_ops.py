import threading
import urllib.parse
import urllib.request

from oscombo.human_apps.inventory_ops import create_fixture, evaluate, make_server


def _post(base, path, fields):
    request = urllib.request.Request(
        base + path,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.url


def test_inventory_fixture_hashes_and_initial_states_are_equal(tmp_path):
    first = create_fixture(tmp_path / "first.sqlite3", "one")
    second = create_fixture(tmp_path / "second.sqlite3", "two")
    assert first["source_content_sha256"] == second["source_content_sha256"]
    assert first["initial_state"] == second["initial_state"]
    assert first["initial_state"]["draft_count"] == 0
    assert first["initial_state"]["receipt_count"] == 0


def test_receipt_and_restock_workflows_have_deterministic_oracles(tmp_path):
    db_path = tmp_path / "inventory.sqlite3"
    create_fixture(db_path, "positive-control")
    server = make_server(db_path, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for page in ("/exceptions", "/policy", "/suppliers", "/inbound", "/receiving", "/packing-slip"):
            with urllib.request.urlopen(base + page, timeout=5) as response:
                assert response.status == 200

        assert _post(base, "/receive/save", {
            "sku": "SKU-D", "lot": "LOT-7721", "quantity": "12", "bin_location": "B-14",
            "warehouse": "West Warehouse", "slip_id": "ASN-7721",
        })[0] == 200
        drafts = [
            ("SKU-A", "Northstar Industrial", 32, "replenish to target 48; include inbound 12; case pack 8"),
            ("SKU-B", "BluePeak Components", 60, "replenish to target 110; include inbound 10; case pack 12"),
            ("SKU-C", "Meadowline Supply", 30, "replenish to target 30; include inbound 4; case pack 10"),
        ]
        for sku, vendor, quantity, reason in drafts:
            assert _post(base, "/restock/save", {
                "sku": sku, "vendor": vendor, "quantity": str(quantity), "reason": reason,
            })[0] == 200

        result = evaluate(db_path)
        assert result["agent"]["success"] is True
        assert result["user"]["success"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_wrong_receipt_or_restock_values_fail_the_oracle(tmp_path):
    db_path = tmp_path / "inventory.sqlite3"
    create_fixture(db_path, "negative-control")
    server = make_server(db_path, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        _post(base, "/receive/save", {
            "sku": "SKU-C", "lot": "LOT-7721", "quantity": "12", "bin_location": "B-14",
            "warehouse": "West Warehouse", "slip_id": "ASN-7721",
        })
        assert evaluate(db_path)["user"]["success"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
