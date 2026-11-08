"""v5.8 bridge tests: recorded scan files and serial TRACE blocks reach /api/scans through a durable outbox,
with stable idempotency keys, and nothing is lost when the server is down."""
import importlib.util
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.signal_processing import generate_synthetic_asv_trace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.path.join(ROOT, "bridge", "serial_bridge.py")
DATA = os.path.join(os.path.dirname(ROOT), "Data")


@pytest.fixture(scope="module")
def bridge():
    spec = importlib.util.spec_from_file_location("serial_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _sender(bridge, client, outbox_path, down=None):
    down = down if down is not None else {"on": False}

    def post(path, payload):
        if down["on"]:
            return 0, "connection refused"
        r = client.post(path, json=payload)
        return r.status_code, r.text
    return bridge.Sender("http://unit-test", None, bridge.Outbox(outbox_path), post=post), down


def test_parse_scan_csv_handles_headers_units_and_separators(bridge):
    P, C = bridge.parse_scan_csv("potential_mV,current_uA\n-1000,0.05\n-995,0.03\n")
    assert P == [-1000.0, -995.0] and C == [0.05, 0.03]
    P, C = bridge.parse_scan_csv("E;I\n-1.000;5e-8\n-0.995;3e-8\n")      # volts and amps
    assert P == [-1000.0, -995.0] and abs(C[0] - 0.05) < 1e-9
    P, C = bridge.parse_scan_csv("-1000\t0.05\n-995\t0.03\n")              # no header, tabs
    assert len(P) == 2
    with open(os.path.join(DATA, "sample_scan_81pt.csv"), encoding="utf-8") as f:
        P, C = bridge.parse_scan_csv(f.read())
    assert len(P) == 81 and P[0] == -1000.0


def test_scalar_line_keeps_qc_and_source(bridge):
    fields = bridge.parse_line("AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10,QC:pass,junk,X:abc")
    p = bridge.build_reading_payload(fields, "BT-01", "AS:6.20,...", "hardware")
    assert p["arsenic_ppb"] == 6.2 and p["qc_status"] == "pass" and p["source_type"] == "hardware"
    assert p["ph"] == 7.1 and p["temperature_c"] == 26.4 and len(p["idempotency_key"]) <= 64
    with pytest.raises(ValueError):
        bridge.build_reading_payload({"PH": 7.0}, "BT-01", "PH:7.0")


def test_scan_payload_key_is_stable_and_bounded(bridge):
    P, C = generate_synthetic_asv_trace(40)
    a = bridge.build_scan_payload(P, C, "W-1", "recorded_replay", file_name="/x/y/scan.csv")
    b = bridge.build_scan_payload(P, C, "W-1", "recorded_replay", file_name="/other/scan.csv")
    assert a["idempotency_key"] == b["idempotency_key"] and a["raw_file_name"] == "scan.csv"
    assert bridge.build_scan_payload(P, C, "W-2", "recorded_replay")["idempotency_key"] != a["idempotency_key"]
    with pytest.raises(ValueError):
        bridge.build_scan_payload(P[:5], C[:5], "W-1", "recorded_replay")
    with pytest.raises(ValueError):
        bridge.build_scan_payload(P, C[:-1], "W-1", "recorded_replay")


def test_file_upload_reaches_api_scans_and_is_idempotent(bridge, client, tmp_path):
    P, C = generate_synthetic_asv_trace(55, seed=9)
    f = tmp_path / "well16_scan.csv"
    f.write_text("potential_mV,current_uA\n" + "\n".join(f"{p},{c}" for p, c in zip(P, C)))
    sender, _ = _sender(bridge, client, str(tmp_path / "outbox.jsonl"))
    assert bridge.upload_file(sender, str(f), "BRG-01", "recorded_replay") is True
    assert bridge.upload_file(sender, str(f), "BRG-01", "recorded_replay") is True
    scans = client.get("/api/scans?device_code=BRG-01").json()
    assert len(scans) == 1 and scans[0]["source_type"] == "recorded_replay" and scans[0]["raw_file_name"] == "well16_scan.csv"
    readings = client.get("/api/readings?device_code=BRG-01").json()
    assert len(readings) == 1 and abs(readings[0]["arsenic_ppb"] - 55) < 4 and readings[0]["is_simulated"] is False
    assert sender.outbox.pending() == []


def test_serial_trace_block_and_scalar_lines(bridge, client, tmp_path):
    sender, _ = _sender(bridge, client, str(tmp_path / "outbox.jsonl"))
    P, C = generate_synthetic_asv_trace(120, seed=3)
    state = None
    for line in ["TRACE_BEGIN"] + [f"{p},{c}" for p, c in zip(P, C)] + ["TRACE_END"]:
        state = bridge.handle_line(sender, line, "BRG-02", "hardware", state)
    assert state is None
    state = bridge.handle_line(sender, "TRACE:" + ";".join(f"{p}:{c}" for p, c in zip(P, C)), "BRG-02", "hardware", None)
    scans = client.get("/api/scans?device_code=BRG-02").json()
    assert len(scans) == 1       # the one-line form of the same points is the same scan
    bridge.handle_line(sender, "AS:8.5,PH:7.2,QC:pass", "BRG-02", "hardware", None)
    readings = client.get("/api/readings?device_code=BRG-02").json()
    assert len(readings) == 2 and {r["source_type"] for r in readings} == {"hardware"}
    assert bridge.handle_line(sender, "garbage line", "BRG-02", "hardware", None) is None


def test_outbox_survives_a_server_outage(bridge, client, tmp_path):
    outbox = str(tmp_path / "outbox.jsonl")
    sender, down = _sender(bridge, client, outbox)
    down["on"] = True
    P, C = generate_synthetic_asv_trace(33, seed=5)
    assert bridge.handle_line(sender, "TRACE:" + ";".join(f"{p}:{c}" for p, c in zip(P, C)), "BRG-03", "hardware", None) is None
    bridge.handle_line(sender, "AS:4.0,QC:pass", "BRG-03", "hardware", None)
    assert len(sender.outbox.pending()) == 2 and client.get("/api/scans?device_code=BRG-03").json() == []
    # a new bridge process (fresh Sender on the same outbox file) delivers them once the server is back
    down["on"] = False
    sender2, _ = _sender(bridge, client, outbox, down)
    assert sender2.flush() == 0
    assert len(client.get("/api/scans?device_code=BRG-03").json()) == 1
    assert len(client.get("/api/readings?device_code=BRG-03").json()) == 2
    # a definitive rejection is dropped, not retried forever
    sender2.send("reading", {"device_code": "BRG-03", "arsenic_ppb": -5, "idempotency_key": "bad-1"})
    assert sender2.outbox.pending() == []
