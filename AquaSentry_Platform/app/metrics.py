"""
Prometheus-style metrics, dependency-free.

Request counts and latency are kept per route *template* ("/api/devices/{device_code}", not the
real code) so the number of series stays small. The text format follows the Prometheus exposition
format 0.0.4, which Prometheus, Grafana Agent, VictoriaMetrics and Netdata all scrape.
"""
from __future__ import annotations

import threading
from typing import Dict, Iterable, List, Tuple

# Latency buckets in seconds: an ESP32 upload should land well under 250 ms on a LAN.
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class RequestMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.count: Dict[Tuple[str, str, str], int] = {}
        self.hist: Dict[Tuple[str, str], List[float]] = {}      # buckets..., sum, count

    def observe(self, method: str, route: str, status: int, seconds: float):
        key = (method, route, f"{status // 100}xx")
        with self._lock:
            self.count[key] = self.count.get(key, 0) + 1
            h = self.hist.setdefault((method, route), [0.0] * (len(BUCKETS) + 2))
            for i, b in enumerate(BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-2] += seconds
            h[-1] += 1

    def reset(self):
        with self._lock:
            self.count.clear()
            self.hist.clear()

    def snapshot(self):
        with self._lock:
            return dict(self.count), {k: list(v) for k, v in self.hist.items()}


REQUESTS = RequestMetrics()


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**kw) -> str:
    if not kw:
        return ""
    return "{" + ",".join(f'{k}="{_esc(v)}"' for k, v in kw.items()) + "}"


def render(gauges: Iterable[Tuple[str, str, str, Dict[str, str], float]]) -> str:
    """gauges: (name, type, help, labels, value). Lines with the same name share one HELP/TYPE."""
    out: List[str] = []
    seen = set()
    for name, mtype, help_text, labels, value in gauges:
        if name not in seen:
            out.append(f"# HELP {name} {help_text}")
            out.append(f"# TYPE {name} {mtype}")
            seen.add(name)
        out.append(f"{name}{_labels(**labels)} {float(value):g}")

    counts, hists = REQUESTS.snapshot()
    out.append("# HELP aquasentry_http_requests_total HTTP requests by route template and status class.")
    out.append("# TYPE aquasentry_http_requests_total counter")
    for (method, route, status), n in sorted(counts.items()):
        out.append(f"aquasentry_http_requests_total{_labels(method=method, route=route, status=status)} {n}")
    out.append("# HELP aquasentry_http_request_duration_seconds Time spent handling HTTP requests.")
    out.append("# TYPE aquasentry_http_request_duration_seconds histogram")
    for (method, route), h in sorted(hists.items()):
        for i, b in enumerate(BUCKETS):
            out.append(f"aquasentry_http_request_duration_seconds_bucket{_labels(method=method, route=route, le=f'{b:g}')} {h[i]:g}")
        out.append(f"aquasentry_http_request_duration_seconds_bucket{_labels(method=method, route=route, le='+Inf')} {h[-1]:g}")
        out.append(f"aquasentry_http_request_duration_seconds_sum{_labels(method=method, route=route)} {h[-2]:.6f}")
        out.append(f"aquasentry_http_request_duration_seconds_count{_labels(method=method, route=route)} {h[-1]:g}")
    return "\n".join(out) + "\n"
