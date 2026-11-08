"""
AquaSentry bridge (v5.8): serial / Bluetooth node -> backend, and recorded scan files -> backend.

Runs on a laptop or Raspberry Pi. Three ways to use it:

  1. A node on a serial or Bluetooth (HC-05 / HC-06) port, one reading per line:
         python bridge/serial_bridge.py --port COM5
     Scalar line (as before):   AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10,QC:pass
     Native scan (v5.8), which the server processes, stores with a checksum and turns into a reading:
         TRACE_BEGIN
         -1100.0,-0.15012
         -1095.0,-0.14936
         ...                      (potential_mV,current_uA; any number of points, 10 or more)
         TRACE_END
     or on one line:  TRACE:-1100.0:-0.15012;-1095.0:-0.14936;...
  2. Recorded scan files (CSV with potential_mV,current_uA columns, as in Data/):
         python bridge/serial_bridge.py --file Data/sample_scan_81pt.csv --device-code WELL-16
     They are uploaded as "recorded_replay": real instrument data played back, never shown as a simulation.
  3. A folder watched for new scan files (a logger that writes one CSV per scan):
         python bridge/serial_bridge.py --watch /media/logger/scans --device-code WELL-16

Every upload is written to a durable outbox (bridge_outbox.jsonl next to this file) BEFORE it is sent and removed
once the server has stored it, so a dropped connection or a crash never loses a scan; the outbox is flushed first
on every start. Every scan carries a stable idempotency key (device code + content hash), so re-sending the same
file or line can never create a second reading.

Install deps: pip install pyserial requests        (pyserial only for --port)
Server key:   --api-key or the AQUASENTRY_API_KEY environment variable (required unless the bridge runs on the
              same computer as the server).
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

DEFAULT_BAUD_RATE = 9600
DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_DEVICE_CODE = "AQUA-001"
OUTBOX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_outbox.jsonl")
MIN_POINTS = 10
MAX_POINTS = 2000


# ---------------------------------------------------------------- parsing
def parse_line(line: str) -> dict:
    """Parse 'AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10,QC:pass' into a dict (numbers as floats, QC as text)."""
    fields: Dict[str, object] = {}
    for part in line.strip().split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key, value = key.strip().upper(), value.strip()
        if key == "QC":
            fields[key] = value.lower()
            continue
        try:
            fields[key] = float(value)
        except ValueError:
            continue  # skip a malformed field rather than crashing the bridge
    return fields


def parse_trace_line(line: str) -> Tuple[List[float], List[float]]:
    """'TRACE:-1100.0:-0.15;-1095.0:-0.149;...' -> (potentials_mV, currents_uA)."""
    body = line.strip()[len("TRACE:"):]
    P: List[float] = []
    C: List[float] = []
    for pair in body.split(";"):
        if ":" not in pair:
            continue
        a, b = pair.split(":", 1)
        try:
            P.append(float(a))
            C.append(float(b))
        except ValueError:
            continue
    return P, C


def parse_scan_csv(text: str) -> Tuple[List[float], List[float]]:
    """A recorded scan file: two numeric columns (potential, current). Header optional; units converted when the
    range makes it obvious (volts -> mV, amps / nanoamps -> µA), the same rule as the dashboard's replay button."""
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        sep = dialect.delimiter
    except csv.Error:
        sep = ","
    P: List[float] = []
    C: List[float] = []
    pi, ci = 0, 1
    for i, row in enumerate(csv.reader(io.StringIO(text), delimiter=sep)):
        cells = [c.strip() for c in row if c.strip() != ""]
        if not cells:
            continue
        if i == 0 and not _is_number(cells[0]):
            low = [c.lower() for c in cells]
            pi = next((k for k, c in enumerate(low) if "pot" in c or "volt" in c or c.endswith("mv") or c == "e"), 0)
            ci = next((k for k, c in enumerate(low) if "cur" in c or c.endswith("ua") or c.endswith("µa") or c == "i"), 1)
            continue
        if len(cells) <= max(pi, ci):
            continue
        try:
            P.append(float(cells[pi]))
            C.append(float(cells[ci]))
        except ValueError:
            continue
    if P:
        span = max(P) - min(P)
        if 0 < span < 5:
            P = [p * 1000.0 for p in P]
        max_abs = max(abs(c) for c in C)
        if max_abs < 1e-3:
            C = [c * 1e6 for c in C]
        elif max_abs > 1e4:
            C = [c / 1000.0 for c in C]
    return P, C


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- payloads
def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def content_key(device_code: str, P: List[float], C: List[float], salt: str = "") -> str:
    """Stable id for a scan: the same points from the same device always get the same key (so a re-sent file or
    a retried line cannot become a second reading)."""
    h = hashlib.sha256()
    h.update(device_code.encode())
    h.update(salt.encode())
    h.update(json.dumps([round(p, 4) for p in P]).encode())
    h.update(json.dumps([round(c, 6) for c in C]).encode())
    return "bridge-" + h.hexdigest()[:40]


def build_reading_payload(fields: dict, device_code: str, raw_line: str, source_type: str = "hardware") -> dict:
    if "AS" not in fields:
        raise ValueError(f"No arsenic ('AS') value found in line: {raw_line!r}")
    payload = {
        "device_code": device_code,
        "arsenic_ppb": fields["AS"],
        "recorded_at": _now_iso(),
        "raw_payload": raw_line.strip()[:500],
        "source_type": source_type,
        "source_label": "Serial bridge",
        "idempotency_key": content_key(device_code, [fields["AS"]], [], salt=raw_line.strip() + _now_iso()[:16])[:64],
    }
    optional_map = {"PH": "ph", "T": "temperature_c", "EC": "conductivity_us_cm", "TURB": "turbidity_ntu",
                    "DO": "dissolved_oxygen_mg_l", "BAT": "battery_pct"}
    for src_key, dest_key in optional_map.items():
        if src_key in fields:
            payload[dest_key] = fields[src_key]
    if fields.get("QC") in ("pass", "fail"):
        payload["qc_status"] = fields["QC"]
    return payload


def build_scan_payload(P: List[float], C: List[float], device_code: str, source_type: str,
                       file_name: Optional[str] = None, recorded_at: Optional[str] = None) -> dict:
    if len(P) != len(C):
        raise ValueError("potential and current columns have different lengths")
    if len(P) < MIN_POINTS:
        raise ValueError(f"a scan needs at least {MIN_POINTS} points (got {len(P)})")
    if len(P) > MAX_POINTS:
        raise ValueError(f"a scan has at most {MAX_POINTS} points (got {len(P)})")
    return {
        "device_code": device_code,
        "potentials_mv": [round(p, 4) for p in P],
        "currents_ua": [round(c, 6) for c in C],
        "source_type": source_type,
        "recorded_at": recorded_at or _now_iso(),
        "raw_file_name": os.path.basename(file_name) if file_name else None,
        "source_label": "Serial bridge" if source_type == "hardware" else "Recorded replay",
        "idempotency_key": content_key(device_code, P, C),
    }


# ---------------------------------------------------------------- durable outbox
class Outbox:
    """Append-only JSONL of uploads not yet confirmed by the server. Written before the first attempt; an entry is
    removed only after a 2xx (stored) or a definitive 4xx (rejected for good: retrying would block the queue)."""

    def __init__(self, path: str = OUTBOX_PATH):
        self.path = path

    def _read(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def _write(self, items: List[dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
        os.replace(tmp, self.path)

    def add(self, kind: str, payload: dict) -> str:
        key = payload.get("idempotency_key") or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:40]
        items = self._read()
        if not any(i.get("key") == key for i in items):
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "kind": kind, "payload": payload, "queued_at": _now_iso()}) + "\n")
        return key

    def remove(self, key: str) -> None:
        self._write([i for i in self._read() if i.get("key") != key])

    def pending(self) -> List[dict]:
        return self._read()


# ---------------------------------------------------------------- sending
class Sender:
    def __init__(self, backend_url: str, api_key: Optional[str], outbox: Outbox,
                 post: Optional[Callable[[str, dict], Tuple[int, str]]] = None):
        self.base = backend_url.rstrip("/")
        if self.base.endswith("/api/readings"):       # old --backend-url form still works
            self.base = self.base[: -len("/api/readings")]
        self.api_key = api_key
        self.outbox = outbox
        self._post = post or self._http_post

    def _http_post(self, path: str, payload: dict) -> Tuple[int, str]:
        import requests
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        try:
            r = requests.post(self.base + path, json=payload, headers=headers, timeout=15)
            return r.status_code, r.text
        except requests.RequestException as e:
            return 0, str(e)

    def send(self, kind: str, payload: dict) -> bool:
        """Queue then send. Returns True when the server stored it (or it was rejected for good and dropped)."""
        key = self.outbox.add(kind, payload)
        return self._deliver(key, kind, payload)

    def _deliver(self, key: str, kind: str, payload: dict) -> bool:
        path = "/api/scans" if kind == "scan" else "/api/readings"
        code, text = self._post(path, payload)
        if 200 <= code < 300:
            self.outbox.remove(key)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            if kind == "scan":
                res = data.get("result") or {}
                pipe = data.get("pipeline") or {}
                print(f"  -> scan #{(data.get('scan') or {}).get('id')} stored"
                      f"{' (duplicate of an earlier upload)' if data.get('duplicate') else ''}: "
                      f"{pipe.get('qc_status', '?')}, {pipe.get('estimated_ug_l')} ug/L, "
                      f"outcome {res.get('screening_outcome')}")
            else:
                print(f"  -> stored. {data.get('label')} ({data.get('screening_outcome')})")
            return True
        if code == 0:
            print(f"  -> server not reachable ({text}); kept in the outbox")
            return False
        if code in (408, 429) or code >= 500:
            print(f"  -> server busy (HTTP {code}); kept in the outbox")
            return False
        print(f"  -> rejected for good (HTTP {code}): {text[:300]}")
        self.outbox.remove(key)
        return True

    def flush(self) -> int:
        """Re-send everything still in the outbox, oldest first. Returns how many are still pending."""
        items = self.outbox.pending()
        if items:
            print(f"Outbox: {len(items)} upload(s) waiting")
        for it in items:
            if not self._deliver(it["key"], it["kind"], it["payload"]):
                break   # the server is down; keep the order and stop hammering it
        return len(self.outbox.pending())


# ---------------------------------------------------------------- modes
def upload_file(sender: Sender, path: str, device_code: str, source_type: str) -> bool:
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        text = f.read()
    P, C = parse_scan_csv(text)
    recorded = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).replace(microsecond=0)
    payload = build_scan_payload(P, C, device_code, source_type, file_name=path,
                                 recorded_at=recorded.isoformat().replace("+00:00", "Z"))
    print(f"[file] {os.path.basename(path)}: {len(P)} points")
    return sender.send("scan", payload)


def watch_folder(sender: Sender, folder: str, device_code: str, source_type: str, poll_s: float = 5.0) -> None:
    seen_path = os.path.join(folder, ".aquasentry_uploaded")
    seen = set()
    if os.path.exists(seen_path):
        with open(seen_path, "r", encoding="utf-8") as f:
            seen = {ln.strip() for ln in f if ln.strip()}
    print(f"Watching {folder} for new scan files (CSV). Press Ctrl+C to stop.")
    while True:
        try:
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith((".csv", ".txt")) or name in seen:
                    continue
                full = os.path.join(folder, name)
                if time.time() - os.path.getmtime(full) < 2:
                    continue   # still being written
                try:
                    ok = upload_file(sender, full, device_code, source_type)
                except (ValueError, OSError) as e:
                    print(f"  -> {name}: {e}")
                    ok = True   # a file that cannot be read will not become readable; do not retry forever
                if ok:
                    seen.add(name)
                    with open(seen_path, "a", encoding="utf-8") as f:
                        f.write(name + "\n")
            sender.flush()
            time.sleep(poll_s)
        except KeyboardInterrupt:
            print("\nStopping bridge.")
            return


def run_serial(sender: Sender, port: str, baud: int, device_code: str, source_type: str) -> None:
    try:
        import serial
    except ImportError:
        print("pyserial is needed for --port: pip install pyserial")
        sys.exit(1)
    print(f"Opening serial port {port} @ {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=5)
    except serial.SerialException as e:
        print(f"ERROR: could not open serial port {port}: {e}")
        sys.exit(1)
    time.sleep(2)  # let the connection settle
    print(f"Listening for readings. Forwarding to {sender.base}")
    print("Press Ctrl+C to stop.\n")
    trace_lines: Optional[List[str]] = None
    last_flush = time.time()
    while True:
        try:
            raw = ser.readline()
            if time.time() - last_flush > 30:
                sender.flush()
                last_flush = time.time()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            trace_lines = handle_line(sender, line, device_code, source_type, trace_lines)
        except KeyboardInterrupt:
            print("\nStopping bridge.")
            break
        except Exception as e:  # never let one bad line crash the whole bridge process
            print(f"  -> unexpected error, continuing: {e}")


def handle_line(sender: Sender, line: str, device_code: str, source_type: str,
                trace_lines: Optional[List[str]]) -> Optional[List[str]]:
    """One line from the node. Scalar readings go straight out; TRACE blocks are collected between TRACE_BEGIN and
    TRACE_END and sent as one scan. Returns the block being collected (None when not inside one)."""
    up = line.upper()
    if up == "TRACE_BEGIN":
        return []
    if up == "TRACE_END":
        if trace_lines is None:
            return None
        P, C = parse_scan_csv("\n".join(trace_lines))
        print(f"[serial] scan block: {len(P)} points")
        _send_scan(sender, P, C, device_code, source_type)
        return None
    if trace_lines is not None:
        trace_lines.append(line)
        return trace_lines
    if up.startswith("TRACE:"):
        P, C = parse_trace_line(line)
        print(f"[serial] scan line: {len(P)} points")
        _send_scan(sender, P, C, device_code, source_type)
        return None
    print(f"[serial] {line}")
    fields = parse_line(line)
    if not fields:
        print("  -> could not parse, skipping")
        return None
    try:
        sender.send("reading", build_reading_payload(fields, device_code, line, source_type))
    except ValueError as e:
        print(f"  -> {e}")
    return None


def _send_scan(sender: Sender, P: List[float], C: List[float], device_code: str, source_type: str) -> None:
    try:
        sender.send("scan", build_scan_payload(P, C, device_code, source_type))
    except ValueError as e:
        print(f"  -> scan not sent: {e}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="AquaSentry bridge: serial node or recorded scan files -> backend")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="Serial port, e.g. COM5 or /dev/rfcomm0")
    src.add_argument("--file", nargs="+", help="Recorded scan CSV file(s) to upload as a replay")
    src.add_argument("--watch", help="Folder to watch for new scan CSV files")
    src.add_argument("--flush", action="store_true", help="Only re-send what is waiting in the outbox")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    parser.add_argument("--backend-url", default=os.environ.get("AQUASENTRY_URL", DEFAULT_BACKEND_URL),
                        help="Server base URL (http://host:8000)")
    parser.add_argument("--device-code", default=DEFAULT_DEVICE_CODE)
    parser.add_argument("--api-key", default=os.environ.get("AQUASENTRY_API_KEY"))
    parser.add_argument("--source", choices=["hardware", "recorded_replay", "simulated"],
                        help="How the server should treat the data (default: hardware for --port, recorded_replay for files)")
    args = parser.parse_args(argv)

    source = args.source or ("hardware" if args.port else "recorded_replay")
    sender = Sender(args.backend_url, args.api_key, Outbox())
    pending = sender.flush()
    if args.flush:
        print(f"{pending} upload(s) still waiting" if pending else "Outbox empty.")
        return 0
    if args.file:
        ok = True
        for path in args.file:
            try:
                ok = upload_file(sender, path, args.device_code, source) and ok
            except (ValueError, OSError) as e:
                print(f"  -> {path}: {e}")
                ok = False
        return 0 if ok else 1
    if args.watch:
        watch_folder(sender, args.watch, args.device_code, source)
        return 0
    run_serial(sender, args.port, args.baud, args.device_code, source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
