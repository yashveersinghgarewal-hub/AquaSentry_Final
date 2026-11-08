"""
AquaSentry Backend API.

Provides:
- Ingestion of electrochemical sensor telemetry from Arduino / LoRa / Bluetooth bridge
- Scientific classification & conservative safety precedence evaluation
- AquaNet-V1 Multimodal Deep Neural Classifier inference
- Multi-contaminant / multi-analyte registry and capability matrix
- Electrochemical voltammetry signal processing (Savitzky-Golay, baseline correction, SNR, QC)
- Data import / export with strict provenance tracking and schema versioning
- AI Chatbot Agent integration with intent classification and grounded context
- SQLite persistence with non-destructive schema migrations
"""

import os
import io
import re
import hmac
import json
import uuid
import asyncio
import ipaddress
import threading
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

import csv
import time as _time
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .database import (engine, get_db, Base, ensure_sqlite_columns, compact_database, ensure_indexes,
                       sqlite_info, backup_database)
from . import security, webhooks, metrics
from .events import HUB
from .trends import analyse as analyse_trend
from .classification import classify_arsenic_neural
from .standards import (
    WHO_GUIDELINE_UG_L,
    BIS_PERMISSIBLE_LIMIT_UG_L,
    HAZARD_THRESHOLD_UG_L,
    LOD_UG_L,
    LOQ_UG_L,
    METHOD_NAME,
    CALIBRATION_SLOPE,
    CALIBRATION_INTERCEPT,
)
from .neural_classifier import forward_pass, NODES_COUNT, SYNAPSES_COUNT
from .analytes import (
    ANALYTE_REGISTRY,
    get_analyte_profile,
    list_supported_analytes,
)
from .signal_processing import (
    process_voltammetry_trace,
    generate_synthetic_asv_trace,
)
from .chat_policy import (
    classify_user_prompt,
    format_grounded_context,
    format_fleet_context,
    offline_answer,
)

# Create tables on startup and apply non-destructive column migrations
Base.metadata.create_all(bind=engine)
ensure_sqlite_columns()
ensure_indexes()
START_TIME = _time.time()

app = FastAPI(
    title="AquaSentry Water Safety & Surveillance API",
    description="Scientific backend and edge neural classifier for autonomous water quality monitoring.",
    version="1.6.0",
)

APP_VERSION = "1.6.0"


def active_model_name() -> str:
    """The model that classifies stored readings (AQUANET_MODEL=v1 switches back to the hand-built V1)."""
    return "AquaNet-V1" if os.getenv("AQUANET_MODEL", "v3").lower() == "v1" else "AquaNet-V3"


def _v3_topology():
    try:
        from .aquanet_v3 import load, _resolve
        sizes = load(_resolve(None))["topology"]
        weights = sum(sizes[i] * sizes[i + 1] for i in range(len(sizes) - 1))
        params = weights + sum(sizes[1:])
        return sizes, sum(sizes), weights, params
    except Exception:
        return [5, 16, 12, 4], 37, 320, 352


V3_SIZES, V3_NODES, V3_WEIGHTS, V3_PARAMS = _v3_topology()


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def _val(x, default):
    """`x or default` treats a real 0 (0 NTU, 0 °C, 0 µS/cm) as missing. This does not."""
    return default if x is None else x


# ---------------------------------------------------------------------------
# Write protection
# ---------------------------------------------------------------------------
# Set AQUASENTRY_API_KEY in .env to require an X-API-Key header on every request that changes data
# (ESP32 uploads, imports, demo loading, admin). Requests from this computer itself (the dashboard
# opened at http://localhost:8000) are always allowed, so the UI keeps working without the key.
# Without a key, writes stay open as before (handy on a home network), and /api/health says so.

def _api_key() -> Optional[str]:
    key = (os.getenv("AQUASENTRY_API_KEY") or "").strip()
    return key or None


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host in ("testclient", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _key_ok(request: Request) -> bool:
    key = _api_key()
    given = request.headers.get("x-api-key") or ""
    return bool(key) and hmac.compare_digest(given.encode(), key.encode())


def _check_device_key(db: Session, device_code: str, request: Request):
    dev = db.query(models.Device).filter_by(device_code=device_code).first()
    if dev is not None and dev.api_key_hash:
        given = request.headers.get("x-api-key")
        if not (security.key_matches(given, dev.api_key_hash) or _key_ok(request)):
            raise HTTPException(status_code=401, detail=f"Device '{device_code}' has its own API key; send it as X-API-Key.")


def require_writer(request: Request):
    """Writes are allowed from this computer, with the global key, or with any registered device key
    (the device key is then checked against the device_code in the body by _check_device_key)."""
    if _api_key() is None or _is_loopback(request) or _key_ok(request):
        return
    given = request.headers.get("x-api-key")
    if given and given.startswith(security.KEY_PREFIX):
        from .database import SessionLocal
        with SessionLocal() as db:
            if db.query(models.Device).filter(models.Device.api_key_hash == security.hash_key(given)).first():
                return
    raise HTTPException(status_code=401, detail="Missing or wrong X-API-Key header (see AQUASENTRY_API_KEY in .env).")


def require_admin(request: Request):
    """Admin actions never run for an anonymous network client, even with writes open."""
    if _is_loopback(request) or _key_ok(request):
        return
    raise HTTPException(status_code=403, detail="Admin endpoints are only available from this computer or with X-API-Key.")


if _api_key() is None:
    print("[AquaSentry] Note: AQUASENTRY_API_KEY is not set, so any device on the network can add readings. "
          "Set it in .env (and DEVICE_API_KEY in the firmware) before deploying.")

cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(security.RateLimitMiddleware)
_PAGES = ["index.html", "market-research.html", "sales-expansion.html", "device-simulator.html", "mas-g1-display.html"]
_FRONTEND_FOR_CSP = __import__("pathlib").Path(os.getenv("AQUASENTRY_FRONTEND_DIR",
                                                          __import__("pathlib").Path(__file__).resolve().parent.parent / "frontend"))
app.add_middleware(security.SecurityHeadersMiddleware,
                   csp=security.build_csp(security.inline_script_hashes(_FRONTEND_FOR_CSP, _PAGES)))


_SAFE_RID = re.compile(r"[^A-Za-z0-9._:-]")


@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):
    """Every response carries X-Request-ID (echoed if the client sent a sane one) and Server-Timing,
    and is counted in /api/metrics under its route template."""
    rid = _SAFE_RID.sub("", request.headers.get("x-request-id") or "")[:64] or uuid.uuid4().hex[:16]
    t0 = _time.perf_counter()
    response = await call_next(request)
    dur = _time.perf_counter() - t0
    response.headers["X-Request-ID"] = rid
    response.headers["Server-Timing"] = f"app;dur={dur * 1000:.1f}"
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:      # static files and 404s: one bucket, never the raw path (unbounded series)
        path = "/api/(unmatched)" if request.url.path.startswith("/api/") else "(static)"
    metrics.REQUESTS.observe(request.method, path, response.status_code, dur)
    return response


def now_utc():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Diagnostics & Health Check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["Meta"])
def health_check(db: Session = Depends(get_db)):
    """Liveness & readiness probe reporting subsystem operational diagnostics."""
    db_ok = False
    try:
        db.execute(func.now())
        db_ok = True
    except Exception:
        db_ok = False

    subsystems = {
        "database": "connected" if db_ok else "disconnected",
        "model_engine": "loaded",
        "model_version": active_model_name(),
        "neural_model": (f"AquaNet-V3 {'-'.join(map(str, V3_SIZES))} ({V3_PARAMS} parameters)"
                         if active_model_name() == "AquaNet-V3" else f"AquaNet-V1 ({SYNAPSES_COUNT} synapses)"),
        "neural_nodes": V3_NODES if active_model_name() == "AquaNet-V3" else NODES_COUNT,
        "neural_synapses": V3_WEIGHTS if active_model_name() == "AquaNet-V3" else SYNAPSES_COUNT,
        "standards_version": "WHO GDWQ 4th ed. / IS 10500:2012 + Amd. 1 (2015, As 10 µg/L no relaxation)",
        "write_auth": "api_key" if _api_key() else "open",
        "app_version": APP_VERSION,
        "uptime_s": round(_time.time() - START_TIME, 1),
        "live_subscribers": HUB.subscriber_count,
        "alert_webhook": ("signed" if os.getenv("ALERT_WEBHOOK_SECRET") else "unsigned") if os.getenv("ALERT_WEBHOOK_URL") else "off",
        "webhook_deliveries": dict(webhooks.STATS),
        **sqlite_info(),
        "ai_chatbot_configured": client is not None,
        "analytes_cataloged": len(ANALYTE_REGISTRY),
        "voltammetry_pipeline": "Savitzky-Golay 5pt + Linear Baseline",
    }

    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": now_utc().isoformat(),
        "subsystems": subsystems,
        "diagnostics": subsystems,
        "standards": {
            "method": METHOD_NAME,
            "lod_ug_l": LOD_UG_L,
            "loq_ug_l": LOQ_UG_L,
            "who_guideline_ug_l": WHO_GUIDELINE_UG_L,
            "bis_limit_ug_l": BIS_PERMISSIBLE_LIMIT_UG_L,
        },
    }


# ---------------------------------------------------------------------------
# Imp 21: Emergency Alert Dispatcher & Recent Cache
# ---------------------------------------------------------------------------

RECENT_EMERGENCY_ALERTS: List[Dict[str, Any]] = []
_ALERT_LOCK = threading.Lock()


ALERTS_RAISED = {"WARNING": 0, "CRITICAL": 0}


def build_alert(classification: str, as_ppb: float, **extra) -> Optional[Dict[str, Any]]:
    """An alert for any reading classified Unsafe or Hazardous (arsenic or otherwise), else None."""
    if classification not in ("Unsafe", "Hazardous"):
        return None
    arsenic_driven = as_ppb >= BIS_PERMISSIBLE_LIMIT_UG_L
    where = f" at {extra['device_code']}" if extra.get("device_code") else ""
    if arsenic_driven:
        msg = (f"Arsenic {as_ppb:.1f} µg/L{where}: above the {BIS_PERMISSIBLE_LIMIT_UG_L:.0f} µg/L limit "
               f"(India IS 10500, no relaxation, and WHO). Do not drink.")
    else:
        msg = f"Water{where} classified {classification}: another reading (pH, turbidity or conductivity) is out of limits."
    return {
        "id": str(uuid.uuid4()),
        "timestamp": now_utc().isoformat(),
        "level": "CRITICAL" if classification == "Hazardous" else "WARNING",
        "classification": classification,
        "contaminant": "Total Arsenic (As)" if arsenic_driven else "Water quality",
        "arsenic_ppb": round(as_ppb, 1),
        "arsenic_mg_l": round(as_ppb / 1000.0, 4),
        "message": msg,
        "action_required": "Do NOT drink. Switch to a tested safe source and send a sample to an accredited lab.",
        **extra,
    }


def dispatch_emergency_alert(data: Dict[str, Any]):
    as_ppb = float(data.get("arsenic_ppb", 0.0) or 0.0)
    alert = build_alert(data.get("classification", ""), as_ppb,
                        source_type=data.get("source_type", "tank_sentry"),
                        source_label=data.get("source_label"), reading_id=data.get("reading_id"),
                        device_code=data.get("device_code"))
    if alert is None:
        return None
    with _ALERT_LOCK:
        RECENT_EMERGENCY_ALERTS.append(alert)
        del RECENT_EMERGENCY_ALERTS[:-50]
        ALERTS_RAISED[alert["level"]] = ALERTS_RAISED.get(alert["level"], 0) + 1
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        # Signed (ALERT_WEBHOOK_SECRET), retried, and on a background thread: never blocks the ESP32's upload.
        webhooks.deliver_in_background(webhook_url, alert)
    return alert


# ---------------------------------------------------------------------------
# Imp 20: Water Screening Report PDF (screening result, NOT a laboratory certificate)
# ---------------------------------------------------------------------------

def _fmt_or_missing(value: Optional[float], fmt: str, unit: str = "") -> str:
    if value is None:
        return "Not measured"
    return f"{value:{fmt}}{(' ' + unit) if unit else ''}"


def reading_fingerprint(reading_dict: Dict[str, Any]) -> str:
    """SHA-256 of the measured values printed on the report, so any later edit can be detected."""
    import hashlib
    import json as _json
    keys = ["reading_id", "recorded_at", "source_type", "arsenic_mg_l", "ph", "conductivity_us_cm",
            "turbidity_ntu", "temperature_c", "predicted_class"]
    canonical = _json.dumps({k: reading_dict.get(k) for k in keys}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_potability_certificate_pdf(reading_dict: Dict[str, Any]) -> bytes:
    """Build a one-page screening report from a stored reading. Every number comes from the reading itself."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    # Vera ships inside ReportLab and has the µ sign (the built-in Helvetica does not print it).
    font, font_bold = "Helvetica", "Helvetica-Bold"
    try:
        import reportlab
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        fdir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        if "AS-Vera" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("AS-Vera", os.path.join(fdir, "Vera.ttf")))
            pdfmetrics.registerFont(TTFont("AS-VeraBd", os.path.join(fdir, "VeraBd.ttf")))
            pdfmetrics.registerFont(TTFont("AS-VeraIt", os.path.join(fdir, "VeraIt.ttf")))
            pdfmetrics.registerFont(TTFont("AS-VeraBI", os.path.join(fdir, "VeraBI.ttf")))
            pdfmetrics.registerFontFamily("AS-Vera", normal="AS-Vera", bold="AS-VeraBd", italic="AS-VeraIt", boldItalic="AS-VeraBI")
        font, font_bold = "AS-Vera", "AS-VeraBd"
    except Exception:
        pass

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName=font_bold, fontSize=18, leading=22,
                                 textColor=colors.HexColor('#13211E'), alignment=1)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName=font, fontSize=9, leading=13,
                                    textColor=colors.HexColor('#4B5D58'), alignment=1)
    header_style = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontName=font_bold, fontSize=11, leading=15,
                                  textColor=colors.HexColor('#1F5F8B'), spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName=font, fontSize=8.5, leading=12,
                                textColor=colors.HexColor('#13211E'))
    cell_style = ParagraphStyle('Cell', parent=body_style, fontSize=8, leading=10)
    head_style = ParagraphStyle('HeadCell', parent=cell_style, fontName=font_bold, textColor=colors.white)
    badge_style = ParagraphStyle('Badge', parent=styles['Normal'], fontName=font_bold, fontSize=12, leading=16, alignment=1)

    story = []
    story.append(Paragraph("AQUASENTRY WATER SCREENING REPORT", title_style))
    story.append(Paragraph("Field screening result from the AquaSentry prototype. Not an accredited laboratory certificate.", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1F5F8B'), spaceAfter=12))

    report_id = f"RPT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{reading_dict.get('reading_id', 'NA')}"
    meta_data = [
        [Paragraph(f"<b>Report ID:</b> {report_id}", body_style),
         Paragraph(f"<b>Sample recorded:</b> {reading_dict.get('recorded_at', 'Unknown')}", body_style)],
        [Paragraph(f"<b>Data source:</b> {reading_dict.get('source_type', 'Unknown')}", body_style),
         Paragraph(f"<b>Method:</b> Anodic stripping voltammetry (MAS-G1) + {reading_dict.get('model_version') or active_model_name()} screening model", body_style)],
        [Paragraph(f"<b>Device:</b> {reading_dict.get('device_code', 'Unknown')}", body_style),
         Paragraph("<b>Reference limits:</b> WHO GDWQ 4th ed. / IS 10500:2012 with Amendment 1 (2015)", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F7F6')), ('PADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#D5DFDB')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    verdict = reading_dict.get("predicted_class") or "Unknown"
    as_mg_l = float(reading_dict.get("arsenic_mg_l") or 0.0)
    as_ug_l = as_mg_l * 1000.0
    tone = {"Safe": ('#E8F4EE', '#1E7F5C'), "Caution": ('#FBF3DC', '#8A6404'), "Unsafe": ('#FBEDE5', '#C2541B'),
            "Hazardous": ('#F8E4E6', '#A3202B')}.get(verdict, ('#F4F7F6', '#4B5D58'))
    badge_bg, badge_color = colors.HexColor(tone[0]), colors.HexColor(tone[1])
    model_line = ""
    if reading_dict.get("model_confidence_pct") is not None:
        model_line = (f"<br/><font size=8 color='#4B5D58'>{reading_dict.get('model_version') or active_model_name()} model confidence: {reading_dict['model_confidence_pct']:.1f}% | "
                      f"uncertainty (normalised entropy): {reading_dict.get('model_entropy', 0.0):.3f}</font>")
    lod_line = ""
    if as_ug_l < LOD_UG_L:
        lod_line = (f"<br/><font size=8 color='#4B5D58'>Arsenic is below the sensor detection limit ({LOD_UG_L:.0f} µg/L). "
                    f"The sensor cannot confirm the WHO limit of 10 µg/L; a laboratory test is required.</font>")
    verdict_table = Table([[Paragraph(
        f"<font color='{badge_color.hexval()}'><b>SCREENING RESULT: {verdict.upper()}</b></font>{model_line}{lod_line}",
        badge_style)]], colWidths=[540])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), badge_bg), ('PADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1.5, badge_color), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Measured values", header_style))
    ph_val = reading_dict.get("ph")
    ec_val = reading_dict.get("conductivity_us_cm")
    turb_val = reading_dict.get("turbidity_ntu")
    temp_val = reading_dict.get("temperature_c")

    if as_ug_l < LOD_UG_L:
        as_status = "Not detected (below sensor LOD): lab test needed to confirm < 10 µg/L"
    elif as_ug_l <= HAZARD_THRESHOLD_UG_L:
        as_status = "Detected: exceeds WHO and IS 10500 (10 µg/L). Unsafe"
    else:
        as_status = "Hazardous (above 150 µg/L)"

    def limit_status(val, ok):
        return "Not measured" if val is None else ("Within limit" if ok(val) else "Outside limit")

    chem_data = [
        ["Parameter", "Measured value", "Limit used", "Status"],
        ["Total arsenic (As)", f"{as_ug_l:.1f} µg/L ({as_mg_l:.4f} mg/L)", "WHO 10 µg/L; IS 10500 10 µg/L (no relaxation)", as_status],
        ["pH", _fmt_or_missing(ph_val, ".2f"), "6.5 - 8.5 (BIS)", limit_status(ph_val, lambda v: 6.5 <= v <= 8.5)],
        ["Turbidity", _fmt_or_missing(turb_val, ".2f", "NTU"), "5 NTU (BIS permissible)", limit_status(turb_val, lambda v: v <= 5.0)],
        ["Conductivity", _fmt_or_missing(ec_val, ".0f", "µS/cm"), "1500 µS/cm (AquaSentry screening)", limit_status(ec_val, lambda v: v <= 1500)],
        ["Temperature", _fmt_or_missing(temp_val, ".1f", "°C"), "No health limit", "Recorded" if temp_val is not None else "Not measured"],
    ]
    chem_data = [[Paragraph(str(v), head_style if i == 0 else cell_style) for v in row] for i, row in enumerate(chem_data)]
    chem_table = Table(chem_data, colWidths=[95, 130, 155, 160])
    chem_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F5F8B')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('PADDING', (0, 0), (-1, -1), 4), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D5DFDB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F7F6')]),
    ]))
    story.append(chem_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Only arsenic is measured by the current hardware. Lead, cadmium and other metals are not tested by this device.", body_style))
    story.append(Spacer(1, 12))

    fingerprint = reading_fingerprint(reading_dict)
    sign_data = [[
        Paragraph("<b>How this result was produced:</b><br/>Stripping-voltammetry peak converted with the stored calibration "
                  f"(slope {CALIBRATION_SLOPE} µA per mg/L, intercept {CALIBRATION_INTERCEPT} µA), then classified by {reading_dict.get('model_version') or active_model_name()} "
                  "with fixed WHO / IS 10500 safety rules applied after the model.", body_style),
        Paragraph(f"<b>Data fingerprint (SHA-256):</b><br/><font size=6.5>{fingerprint[:32]}<br/>{fingerprint[32:]}</font><br/>"
                  "Recomputed from the values on this page; any change to them changes this code.", body_style),
    ]]
    sign_table = Table(sign_data, colWidths=[300, 240])
    sign_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#74867F')), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EDF2F0')),
        ('PADDING', (0, 0), (-1, -1), 6), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Important:</b> AquaSentry is a screening prototype, not an ISO 17025 accredited laboratory instrument. "
                           "Confirm results with an accredited laboratory (ICP-MS or HG-AAS) before declaring water fit for drinking.", body_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Device Helpers
# ---------------------------------------------------------------------------

def _get_or_create_device(db: Session, device_code: str, firmware_version: Optional[str] = None) -> models.Device:
    device = db.query(models.Device).filter_by(device_code=device_code).first()
    ts = now_utc()
    if device is None:
        device = models.Device(
            device_code=device_code,
            first_seen=ts,
            last_seen=ts,
            status="online",
            firmware_version=firmware_version or None,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = ts
        if firmware_version:
            device.firmware_version = firmware_version
        db.commit()
    return device


def _utc(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Readings: Ingest (Called by Arduino / LoRa / Bluetooth Bridge)
# ---------------------------------------------------------------------------

def _reading_response(reading: "models.Reading", eval_res, prefix: str = "") -> schemas.ReadingResponse:
    return schemas.ReadingResponse(
        reading=schemas.ReadingOut.model_validate(reading),
        label=eval_res.label,
        severity=eval_res.severity,
        message=f"{prefix}{eval_res.message}",
        action=eval_res.action,
        analytical_status=eval_res.analytical_status,
        regulatory_tier=eval_res.regulatory_tier,
        is_safe_to_drink=eval_res.is_safe_to_drink,
        uncertainty_ppb=eval_res.uncertainty_ppb,
        is_simulated=bool(reading.is_simulated),
        disclaimer=eval_res.disclaimer,
    )


def _classify_stored(rec: "models.Reading"):
    return classify_arsenic_neural(
        arsenic_ppb=rec.arsenic_ppb,
        ph=_val(rec.ph, 7.2),
        conductivity_us_cm=_val(rec.conductivity_us_cm, 400.0),
        turbidity_ntu=_val(rec.turbidity_ntu, 2.0),
        temperature_c=_val(rec.temperature_c, 24.0),
        source_type=rec.source_type or "simulated",
    )


@app.post("/api/readings", response_model=schemas.ReadingResponse, tags=["Readings"],
          dependencies=[Depends(require_writer)])
def create_reading(payload: schemas.ReadingCreate, request: Request, db: Session = Depends(get_db)):
    """
    Ingest a new arsenic reading from the autonomous vessel or simulator.
    Evaluates risk with conservative public health precedence rules and stores full audit lineage.
    """
    # Idempotency check: if an idempotency key was supplied and already exists, return existing reading
    if payload.idempotency_key:
        existing = db.query(models.Reading).filter_by(idempotency_key=payload.idempotency_key).first()
        if existing:
            # Same reading re-sent (e.g. the ESP32 retrying after a timeout): return what was stored.
            return _reading_response(existing, _classify_stored(existing), prefix="[Idempotent Cache Hit] ")

    # A device with its own key must use it: nobody else on the network can post as that device.
    _check_device_key(db, payload.device_code, request)

    try:
        eval_res = classify_arsenic_neural(
            arsenic_ppb=payload.arsenic_ppb,
            ph=_val(payload.ph, 7.2),
            conductivity_us_cm=_val(payload.conductivity_us_cm, 400.0),
            turbidity_ntu=_val(payload.turbidity_ntu, 2.0),
            temperature_c=_val(payload.temperature_c, 24.0),
            source_type=payload.source_type or "simulated",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    device = _get_or_create_device(db, payload.device_code, payload.firmware_version)
    is_sim = payload.source_type != "hardware"
    ts = now_utc()

    reading = models.Reading(
        device_id=device.id,
        arsenic_ppb=payload.arsenic_ppb,
        classification=eval_res.label,
        analytical_status=eval_res.analytical_status,
        regulatory_tier=eval_res.regulatory_tier,
        is_safe_to_drink=eval_res.is_safe_to_drink,
        uncertainty_ppb=eval_res.uncertainty_ppb,
        confidence=_val(payload.confidence, 0.95),
        source_type=payload.source_type or "simulated",
        is_simulated=is_sim,
        method_version=METHOD_NAME,
        model_version=active_model_name(),
        idempotency_key=payload.idempotency_key,
        ph=payload.ph,
        temperature_c=payload.temperature_c,
        conductivity_us_cm=payload.conductivity_us_cm,
        turbidity_ntu=payload.turbidity_ntu,
        dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
        latitude=payload.latitude,
        longitude=payload.longitude,
        battery_pct=payload.battery_pct,
        source_label=payload.source_label,
        recorded_at=payload.recorded_at or ts,
        received_at=ts,
        raw_payload=payload.raw_payload,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    HUB.publish("reading", {"id": reading.id, "device_code": payload.device_code, "arsenic_ppb": reading.arsenic_ppb,
                            "classification": eval_res.label, "recorded_at": _utc(reading.recorded_at),
                            "source_type": reading.source_type})
    # Imp 21: alert on every Unsafe / Hazardous verdict (not only arsenic, and at the current 10 µg/L limit)
    alert = dispatch_emergency_alert({
        "arsenic_ppb": reading.arsenic_ppb,
        "source_type": reading.source_type,
        "source_label": reading.source_label,
        "classification": eval_res.label,
        "reading_id": reading.id,
        "device_code": payload.device_code,
    })
    if alert:
        HUB.publish("alert", alert)

    return _reading_response(reading, eval_res)


# ---------------------------------------------------------------------------
# Readings: Query & Historical Search
# ---------------------------------------------------------------------------

@app.get("/api/readings", response_model=List[schemas.ReadingOut], tags=["Readings"])
def list_readings(
    response: Response,
    device_code: Optional[str] = Query(None, description="Filter by device code"),
    classification: Optional[str] = Query(None, description="Filter by classification tier"),
    source_type: Optional[str] = Query(None, description="Filter by source_type (simulated | hardware | manual_import)"),
    is_simulated: Optional[bool] = Query(None, description="Filter by simulated vs live"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Newest first. The total number of matching readings is in the X-Total-Count header, for paging."""
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    if classification:
        q = q.filter(models.Reading.classification == classification)
    if source_type:
        q = q.filter(models.Reading.source_type == source_type)
    if is_simulated is not None:
        q = q.filter(models.Reading.is_simulated == is_simulated)

    response.headers["X-Total-Count"] = str(q.order_by(None).count())
    q = q.order_by(models.Reading.recorded_at.desc()).offset(offset).limit(limit)
    return q.all()


@app.get("/api/readings/latest", response_model=schemas.ReadingOut, tags=["Readings"])
def latest_reading(device_code: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    reading = q.order_by(models.Reading.recorded_at.desc()).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings found yet.")
    return reading


@app.get("/api/readings/history", response_model=List[schemas.HistoryPoint], tags=["Readings"])
def reading_history(
    device_code: Optional[str] = Query(None, description="One device, or all devices if omitted"),
    hours: float = Query(24 * 30, gt=0, le=24 * 366, description="How far back to look"),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Compact arsenic history for trend charts, oldest first."""
    since = (now_utc() - timedelta(hours=hours)).replace(tzinfo=None)
    q = db.query(models.Reading, models.Device.device_code).join(models.Device).filter(models.Reading.recorded_at >= since)
    if device_code:
        q = q.filter(models.Device.device_code == device_code)
    rows = q.order_by(models.Reading.recorded_at.desc()).limit(limit).all()
    return [schemas.HistoryPoint(t=_utc(r.recorded_at), ppb=round(r.arsenic_ppb, 2), cls=r.classification, device_code=code)
            for r, code in reversed(rows)]


LOW_BATTERY_PCT = float(os.getenv("LOW_BATTERY_PCT", "15"))

# Hardware nodes test once an hour (SAMPLE_INTERVAL_MS in the firmware); a full test with re-scans takes up to ~11 min.
DEVICE_EXPECTED_INTERVAL_MIN = float(os.getenv("DEVICE_EXPECTED_INTERVAL_MIN", "60"))


def _device_points(db: Session, device_id: int, days: float = 180):
    since = (now_utc() - timedelta(days=days)).replace(tzinfo=None)
    rows = (db.query(models.Reading.recorded_at, models.Reading.arsenic_ppb)
            .filter(models.Reading.device_id == device_id, models.Reading.recorded_at >= since)
            .order_by(models.Reading.recorded_at.asc()).all())
    return [(_utc(t), float(v)) for t, v in rows]


def _device_status(d: "models.Device", latest) -> tuple:
    hardware = bool(latest is not None and latest.source_type == "hardware")
    seen = _utc(d.last_seen)
    mins = round((now_utc() - seen).total_seconds() / 60.0, 1) if seen else None
    if not hardware:
        st = "demo"
    elif mins is not None and mins <= DEVICE_EXPECTED_INTERVAL_MIN * 1.5:
        st = "online"
    elif mins is not None and mins <= DEVICE_EXPECTED_INTERVAL_MIN * 3:
        st = "late"
    else:
        st = "offline"
    return st, mins, hardware, seen


# Trend results keyed by everything that can change them: a new, edited or deleted reading changes the
# count or the newest id, and the 90-day window moves on once a day. Small LRU, thread-safe.
_TREND_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_TREND_LOCK = threading.Lock()
TREND_STATS = {"hits": 0, "misses": 0}


def device_trend_cached(db: Session, device_id: int, days: float = 90) -> dict:
    n, max_id = (db.query(func.count(models.Reading.id), func.max(models.Reading.id))
                 .filter(models.Reading.device_id == device_id).one())
    key = (device_id, days, n, max_id, now_utc().date())
    with _TREND_LOCK:
        if key in _TREND_CACHE:
            _TREND_CACHE.move_to_end(key)
            TREND_STATS["hits"] += 1
            return _TREND_CACHE[key]
    t = analyse_trend(_device_points(db, device_id, days), lod=LOD_UG_L)
    with _TREND_LOCK:
        TREND_STATS["misses"] += 1
        _TREND_CACHE[key] = t
        while len(_TREND_CACHE) > 256:
            _TREND_CACHE.popitem(last=False)
    return t


def _device_out(db: Session, d: "models.Device", counts: dict, unsafe: dict, with_trend: bool = True) -> schemas.DeviceStatusOut:
    latest = (db.query(models.Reading).filter(models.Reading.device_id == d.id)
              .order_by(models.Reading.recorded_at.desc()).first())
    st, mins, hardware, seen = _device_status(d, latest)
    trend = None
    if with_trend and hardware:
        t = device_trend_cached(db, d.id, 90)
        trend = schemas.TrendSummary(direction=t["direction"], significant=t.get("significant", False),
                                     sen_slope_ug_per_week=t.get("sen_slope_ug_per_week"),
                                     p_value=(t.get("mann_kendall") or {}).get("p_value"),
                                     days_to_next_limit=(t.get("projection") or {}).get("days"),
                                     next_limit_ug_l=(t.get("projection") or {}).get("limit_ug_l"),
                                     message=t.get("message"))
    return schemas.DeviceStatusOut(
        device_code=d.device_code, firmware_version=d.firmware_version if hardware else None,
        first_seen=_utc(d.first_seen), last_seen=seen, status=st, minutes_since_seen=mins,
        reading_count=int(counts.get(d.id, 0)), unsafe_count=int(unsafe.get(d.id, 0)), is_hardware=hardware,
        has_device_key=bool(d.api_key_hash), trend=trend,
        latest=schemas.DeviceLatestOut(arsenic_ppb=latest.arsenic_ppb, classification=latest.classification,
                                       recorded_at=_utc(latest.recorded_at),
                                       battery_pct=latest.battery_pct) if latest else None,
    )


def _counts(db: Session):
    counts = dict(db.query(models.Reading.device_id, func.count(models.Reading.id)).group_by(models.Reading.device_id).all())
    unsafe = dict(db.query(models.Reading.device_id, func.count(models.Reading.id))
                  .filter(models.Reading.classification.in_(["Unsafe", "Hazardous"]))
                  .group_by(models.Reading.device_id).all())
    return counts, unsafe


@app.get("/api/devices", response_model=List[schemas.DeviceStatusOut], tags=["Devices"])
def list_devices(db: Session = Depends(get_db)):
    """Every device that has sent data, with online / late / offline status, its latest result and,
    for hardware nodes, the arsenic trend (Mann-Kendall + Sen's slope over 90 days)."""
    counts, unsafe = _counts(db)
    out = [_device_out(db, d, counts, unsafe) for d in db.query(models.Device).all()]
    rank = {"online": 0, "late": 1, "offline": 2, "demo": 3}
    out.sort(key=lambda x: (rank[x.status], -(x.last_seen.timestamp() if x.last_seen else 0)))
    return out


def _device_or_404(db: Session, code: str) -> "models.Device":
    d = db.query(models.Device).filter_by(device_code=code).first()
    if d is None:
        raise HTTPException(status_code=404, detail=f"No device called '{code}'.")
    return d


@app.get("/api/devices/{device_code}", tags=["Devices"])
def device_detail(device_code: str, db: Session = Depends(get_db)):
    """One device: status, trend, the last 20 readings and verdict counts."""
    d = _device_or_404(db, device_code)
    counts, unsafe = _counts(db)
    base = _device_out(db, d, counts, unsafe).model_dump(mode="json")
    recent = (db.query(models.Reading).filter(models.Reading.device_id == d.id)
              .order_by(models.Reading.recorded_at.desc()).limit(20).all())
    by_class = dict(db.query(models.Reading.classification, func.count(models.Reading.id))
                    .filter(models.Reading.device_id == d.id).group_by(models.Reading.classification).all())
    base["recent"] = [{"id": r.id, "recorded_at": _utc(r.recorded_at).isoformat(), "arsenic_ppb": r.arsenic_ppb,
                       "classification": r.classification, "ph": r.ph, "turbidity_ntu": r.turbidity_ntu,
                       "conductivity_us_cm": r.conductivity_us_cm, "temperature_c": r.temperature_c} for r in recent]
    base["by_classification"] = by_class
    return base


@app.get("/api/devices/{device_code}/trend", tags=["Devices"])
def device_trend(device_code: str, days: float = Query(90, gt=1, le=3650), db: Session = Depends(get_db)):
    """Is arsenic at this source rising? Mann-Kendall trend test (tie-corrected, non-detects set to the
    detection limit) with Sen's slope, plus a straight-line projection to the next limit."""
    d = _device_or_404(db, device_code)
    return {"device_code": d.device_code, "days": days, **device_trend_cached(db, d.id, days)}


@app.post("/api/admin/devices/{device_code}/key", tags=["Admin"], dependencies=[Depends(require_admin)])
def create_device_key(device_code: str, db: Session = Depends(get_db)):
    """Give a device its own API key (shown once; only its hash is stored). Replaces any previous key.
    Put it in DEVICE_API_KEY on the ESP32 or in its setup page."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,64}", device_code):
        raise HTTPException(status_code=422, detail="Device codes use letters, digits, - and _ (2-64 characters).")
    d = _get_or_create_device(db, device_code)
    key = security.new_device_key()
    d.api_key_hash, d.api_key_hint = security.hash_key(key), key[:8]
    db.commit()
    return {"device_code": d.device_code, "api_key": key, "hint": d.api_key_hint,
            "note": "Store this now: the server keeps only a hash and cannot show it again."}


@app.delete("/api/admin/devices/{device_code}/key", tags=["Admin"], dependencies=[Depends(require_admin)])
def revoke_device_key(device_code: str, db: Session = Depends(get_db)):
    d = _device_or_404(db, device_code)
    d.api_key_hash = d.api_key_hint = None
    db.commit()
    return {"device_code": d.device_code, "status": "revoked"}


@app.get("/api/events", tags=["Live"])
async def live_events(request: Request, max_events: int = Query(0, ge=0, le=10000,
                      description="Stop after this many events (0 = keep streaming)")):
    """Server-Sent Events: `reading` for every stored reading, `alert` for Unsafe / Hazardous verdicts,
    and a comment heartbeat every 15 s. Browsers reconnect automatically (EventSource)."""
    HUB.bind_loop(asyncio.get_running_loop())
    q = HUB.subscribe()
    if q is None:
        raise HTTPException(status_code=503, detail="Too many live connections; try again shortly.")

    async def stream():
        sent = 0
        try:
            yield "retry: 5000\n: connected\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    continue
                yield msg
                sent += 1
                if max_events and sent >= max_events:
                    break
        finally:
            HUB.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/metrics", tags=["Meta"], response_class=Response)
def prometheus_metrics(request: Request, db: Session = Depends(get_db)):
    """Prometheus text format: readings by verdict and source, devices by status, alerts, webhook
    deliveries, live connections, trend-cache efficiency, and per-route request counts and latency.
    Set METRICS_PUBLIC=0 to restrict it to this computer and holders of AQUASENTRY_API_KEY."""
    if os.getenv("METRICS_PUBLIC", "1") == "0" and not (_is_loopback(request) or _key_ok(request)):
        raise HTTPException(status_code=403, detail="Metrics are restricted (METRICS_PUBLIC=0).")
    g = []
    for cls, src, n in (db.query(models.Reading.classification, models.Reading.source_type, func.count(models.Reading.id))
                        .group_by(models.Reading.classification, models.Reading.source_type).all()):
        g.append(("aquasentry_readings", "gauge", "Stored readings by verdict and source.",
                  {"classification": cls or "unknown", "source_type": src or "unknown"}, n))
    if not g:
        g.append(("aquasentry_readings", "gauge", "Stored readings by verdict and source.",
                  {"classification": "none", "source_type": "none"}, 0))
    by_status = {"online": 0, "late": 0, "offline": 0, "demo": 0}
    for d in db.query(models.Device).all():
        latest = (db.query(models.Reading.source_type).filter(models.Reading.device_id == d.id)
                  .order_by(models.Reading.recorded_at.desc()).first())
        st = _device_status(d, latest)[0]
        by_status[st] = by_status.get(st, 0) + 1
    for st, n in by_status.items():
        g.append(("aquasentry_devices", "gauge", "Sensor nodes by reporting status.", {"status": st}, n))
    with _ALERT_LOCK:
        raised = dict(ALERTS_RAISED)
    for level, n in raised.items():
        g.append(("aquasentry_alerts_raised_total", "counter", "Unsafe / Hazardous alerts raised since start.", {"level": level}, n))
    for outcome, n in webhooks.STATS.items():
        g.append(("aquasentry_webhook_deliveries_total", "counter", "Alert webhook attempts by outcome.", {"outcome": outcome}, n))
    for k, n in TREND_STATS.items():
        g.append(("aquasentry_trend_cache_total", "counter", "Trend cache lookups.", {"result": k}, n))
    g.append(("aquasentry_live_subscribers", "gauge", "Open Server-Sent Events connections.", {}, HUB.subscriber_count))
    g.append(("aquasentry_uptime_seconds", "gauge", "Seconds since the server started.", {}, round(_time.time() - START_TIME, 1)))
    g.append(("aquasentry_build_info", "gauge", "Version information.", {"version": APP_VERSION, "model": active_model_name()}, 1))
    return Response(metrics.render(g), media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# System Aggregated Statistics
# ---------------------------------------------------------------------------

@app.get("/api/stats", response_model=schemas.StatsOut, tags=["Meta"])
def get_stats(device_code: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)

    total = q.count()
    sim_count = q.filter(models.Reading.is_simulated == True).count()
    hw_count = q.filter(models.Reading.is_simulated == False).count()
    hazard_count = q.filter(models.Reading.classification == "Hazardous").count()

    avg = db.query(func.avg(models.Reading.arsenic_ppb))
    if device_code:
        avg = avg.join(models.Device).filter(models.Device.device_code == device_code)
    avg_value = avg.scalar()

    devices_count = db.query(models.Device).count()
    if device_code:
        devices_count = db.query(models.Device).filter(models.Device.device_code == device_code).count()

    return schemas.StatsOut(
        total_readings=total,
        total_devices=devices_count,
        average_arsenic_ppb=round(avg_value, 2) if avg_value is not None else None,
        hazardous_count=hazard_count,
        simulated_count=sim_count,
        hardware_count=hw_count,
        method_lod_ug_l=LOD_UG_L,
        units="µg/L (ppb)",
        timestamp=now_utc(),
    )


# ---------------------------------------------------------------------------
# Dashboard Projection (Supports True Empty State)
# ---------------------------------------------------------------------------

@app.get("/api/dashboard/latest", response_model=schemas.DashboardReading, tags=["Dashboard"])
def dashboard_latest(device_code: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    reading = q.order_by(models.Reading.recorded_at.desc()).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings found yet.")

    confirmed_count = 0
    if reading.classification in ("Unsafe", "Hazardous"):
        # SQLite stores naive UTC datetimes, so compare against a naive UTC cutoff.
        cutoff = (now_utc() - timedelta(hours=24)).replace(tzinfo=None)
        confirmed_count = (
            db.query(models.Reading.device_id)
            .filter(
                models.Reading.classification.in_(["Unsafe", "Hazardous"]),
                models.Reading.recorded_at >= cutoff,
                models.Reading.device_id != reading.device_id,
            )
            .distinct()
            .count()
        )

    rec_time = reading.recorded_at
    if rec_time.tzinfo is None:
        rec_time = rec_time.replace(tzinfo=timezone.utc)
    patrol_minutes = max(
        0.0,
        round((now_utc() - rec_time).total_seconds() / 60.0, 1),
    )
    is_stale = patrol_minutes > 60.0

    as_mg_l = round(reading.arsenic_ppb / 1000.0, 4)
    unc_mg_l = round((reading.uncertainty_ppb or 5.0) / 1000.0, 4)

    disclaimer = (
        "SCREENING ADVISORY: This reading is an autonomous field screening indicator. "
        "It does not constitute an accredited laboratory potability certification."
    )

    return schemas.DashboardReading(
        contaminant="Arsenic (As)",
        value=as_mg_l,
        value_ppb=round(reading.arsenic_ppb, 2),
        unit="mg/L",
        safeLimit=round(WHO_GUIDELINE_UG_L / 1000.0, 3),
        confidencePct=round(reading.confidence * 100, 1) if reading.confidence is not None else 95.0,
        confirmedByHomes=confirmed_count,
        source=reading.source_label or "Water Body Survey",
        detectedAt=rec_time.strftime("%H:%M UTC"),
        detectedAtIso=rec_time.isoformat(),
        batteryPct=reading.battery_pct,
        lastPatrolMin=patrol_minutes,
        nextPatrolMin=None,
        classification=reading.classification,
        analyticalStatus=reading.analytical_status or "within_calibrated_range",
        regulatoryTier=reading.regulatory_tier or "Caution",
        isSafeToDrink=reading.is_safe_to_drink,
        isSimulated=reading.is_simulated if reading.is_simulated is not None else True,
        isStale=is_stale,
        uncertaintyMgL=unc_mg_l,
        methodLOD=round(LOD_UG_L / 1000.0, 3),
        disclaimer=disclaimer,
        analytical_status=reading.analytical_status or "within_calibrated_range",
        regulatory_tier=reading.regulatory_tier or "Caution",
        is_safe_to_drink=reading.is_safe_to_drink,
        is_simulated=reading.is_simulated if reading.is_simulated is not None else True,
        is_stale=is_stale,
        uncertainty_ppb=reading.uncertainty_ppb or 5.0,
        synapses_count=V3_WEIGHTS if active_model_name() == "AquaNet-V3" else SYNAPSES_COUNT,
        method_lod_ug_l=LOD_UG_L,
    )


# ---------------------------------------------------------------------------
# Multi-Contaminant & Analyte Registry Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/analytes", response_model=List[schemas.AnalyteCapabilityOut], tags=["Contaminants"])
def get_analytes_catalog():
    """Retrieve full catalog of registered water contaminants, sensor capabilities, and standards."""
    analytes = list_supported_analytes()
    out = []
    for a in analytes:
        stds_dict = {}
        for k, s in a.standards.items():
            stds_dict[k] = schemas.RegulatoryLimitOut(
                standard_name=s.standard_name,
                jurisdiction=s.jurisdiction,
                acceptable_limit=s.acceptable_limit,
                permissible_limit=s.permissible_limit,
                unit=s.unit,
                citation=s.citation,
                effective_edition=s.effective_edition,
            )
        out.append(
            schemas.AnalyteCapabilityOut(
                identifier=a.identifier,
                name=a.name,
                chemical_formula=a.chemical_formula,
                support_status=a.support_status.value,
                modality=a.modality.value,
                method_name=a.method_name,
                sensor_model=a.sensor_model,
                canonical_unit=a.canonical_unit,
                lod_ug_l=a.lod_ug_l,
                loq_ug_l=a.loq_ug_l,
                cal_range_min_ug_l=a.cal_range_min_ug_l,
                cal_range_max_ug_l=a.cal_range_max_ug_l,
                sample_prep_required=a.sample_prep_required,
                known_interferences=a.known_interferences,
                standards=stds_dict,
                health_significance=a.health_significance,
                operational_notes=a.operational_notes,
                is_actively_monitored_by_hardware=a.is_actively_monitored_by_hardware,
            )
        )
    return out


@app.get("/api/analytes/{analyte_id}", response_model=schemas.AnalyteCapabilityOut, tags=["Contaminants"])
def get_analyte_detail(analyte_id: str):
    """Retrieve detailed capability profile for a single analyte."""
    a = get_analyte_profile(analyte_id)
    if not a:
        raise HTTPException(status_code=404, detail=f"Analyte '{analyte_id}' not found in registry.")

    stds_dict = {}
    for k, s in a.standards.items():
        stds_dict[k] = schemas.RegulatoryLimitOut(
            standard_name=s.standard_name,
            jurisdiction=s.jurisdiction,
            acceptable_limit=s.acceptable_limit,
            permissible_limit=s.permissible_limit,
            unit=s.unit,
            citation=s.citation,
            effective_edition=s.effective_edition,
        )
    return schemas.AnalyteCapabilityOut(
        identifier=a.identifier,
        name=a.name,
        chemical_formula=a.chemical_formula,
        support_status=a.support_status.value,
        modality=a.modality.value,
        method_name=a.method_name,
        sensor_model=a.sensor_model,
        canonical_unit=a.canonical_unit,
        lod_ug_l=a.lod_ug_l,
        loq_ug_l=a.loq_ug_l,
        cal_range_min_ug_l=a.cal_range_min_ug_l,
        cal_range_max_ug_l=a.cal_range_max_ug_l,
        sample_prep_required=a.sample_prep_required,
        known_interferences=a.known_interferences,
        standards=stds_dict,
        health_significance=a.health_significance,
        operational_notes=a.operational_notes,
        is_actively_monitored_by_hardware=a.is_actively_monitored_by_hardware,
    )


# ---------------------------------------------------------------------------
# Electrochemical Voltammetry Signal Processing Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/voltammetry/process", response_model=schemas.VoltammetryProcessResponse, tags=["Electrochemistry"])
def process_voltammetry(payload: schemas.VoltammetryProcessRequest):
    """
    Process raw potentiostat scan arrays through 5-point Savitzky-Golay smoothing,
    linear baseline fitting, SNR estimation, and peak stripping current quantification.
    """
    try:
        res = process_voltammetry_trace(
            potentials_mv=payload.potentials_mv,
            currents_ua=payload.currents_ua,
            target_peak_mv=payload.target_peak_mv or -800.0,
            search_window_mv=payload.search_window_mv or 60.0,
            filter_mode=payload.filter_mode or "savitzky_golay",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    peak_out = None
    if res.peak:
        peak_out = schemas.PeakCharacteristicsOut(
            peak_potential_mv=res.peak.peak_potential_mv,
            peak_current_raw_ua=res.peak.peak_current_raw_ua,
            baseline_current_ua=res.peak.baseline_current_ua,
            net_peak_height_ua=res.peak.net_peak_height_ua,
            peak_area_ua_mv=res.peak.peak_area_ua_mv,
            half_height_width_mv=res.peak.half_height_width_mv,
            snr=res.peak.snr,
            baseline_residual_variance=res.peak.baseline_residual_variance,
            is_valid_peak=res.peak.is_valid_peak,
            qc_flags=res.peak.qc_flags,
        )

    return schemas.VoltammetryProcessResponse(
        estimated_arsenic_ug_l=res.estimated_arsenic_ug_l,
        estimated_arsenic_mg_l=res.estimated_arsenic_mg_l,
        filter_type=res.filter_type,
        qc_status=res.qc_status,
        qc_messages=res.qc_messages,
        peak=peak_out,
        raw_potentials_mv=res.raw_potentials_mv,
        raw_currents_ua=res.raw_currents_ua,
        smoothed_currents_ua=res.smoothed_currents_ua,
        baseline_currents_ua=res.baseline_currents_ua,
        subtracted_currents_ua=res.subtracted_currents_ua,
    )


@app.get("/api/voltammetry/sample-trace", response_model=schemas.SyntheticTraceResponse, tags=["Electrochemistry"])
def get_sample_voltammetry_trace(
    arsenic_ppb: float = Query(45.0, ge=0.0, le=1000.0, description="Concentration to synthesize trace for"),
    snr_db: float = Query(24.0, ge=6.0, le=50.0, description="Signal-to-noise ratio in decibels"),
):
    """Generate a physically parameterized synthetic ASV trace for software testing and calibration."""
    pots, currents = generate_synthetic_asv_trace(arsenic_ppb=arsenic_ppb, snr_db=snr_db)
    return schemas.SyntheticTraceResponse(
        arsenic_ppb=arsenic_ppb,
        potentials_mv=pots,
        currents_ua=currents,
        method="ASV-MAS-G1 Synthetic Model",
        is_synthetic=True,
    )


# ---------------------------------------------------------------------------
# Data Import & Export Endpoints
# ---------------------------------------------------------------------------

# Column detection shared by preview and commit. Columns are split into words, so "class", "basin" or
# "measured_at" are no longer mistaken for arsenic and "recorded_at" is no longer read as conductivity.
_COLUMN_SYNONYMS = {
    "arsenic_ppb": [("arsenic", "ppb"), ("arsenic", "ug", "l"), ("as", "ppb"), ("as", "ug", "l"), ("arsenic", "ugl"), ("as", "ugl")],
    "arsenic_mg_l": [("arsenic", "mg", "l"), ("as", "mg", "l"), ("arsenic", "mgl"), ("as", "mgl"), ("arsenic", "ppm")],
    "arsenic": [("arsenic",), ("as",)],
    "ph": [("ph",)],
    "conductivity_us_cm": [("conductivity",), ("ec",), ("cond",), ("conductance",)],
    "turbidity_ntu": [("turbidity",), ("turb",), ("ntu",)],
    "temperature_c": [("temperature",), ("temp",), ("water", "temp")],
    "latitude": [("latitude",), ("lat",)],
    "longitude": [("longitude",), ("lon",), ("lng",), ("long",)],
    "recorded_at": [("recorded", "at"), ("sampled", "at"), ("timestamp",), ("date",), ("datetime",), ("sample", "date"), ("time",)],
    "sample_id": [("sample", "id"), ("sample",), ("id",), ("idempotency", "key")],
    "source_label": [("source", "label"), ("location",), ("site",), ("station",), ("well",)],
}


def _tokens(name: str):
    import re as _re
    return [t for t in _re.split(r"[^a-z0-9]+", name.lower().replace("µ", "u").replace("μ", "u")) if t]


def detect_columns(cols: List[str]) -> Dict[str, str]:
    """Map our field names to the user's column names. Most specific synonym wins; each column used once."""
    mapping: Dict[str, str] = {}
    used = set()
    for field, patterns in _COLUMN_SYNONYMS.items():
        for pat in patterns:
            for c in cols:
                if c in used:
                    continue
                toks = _tokens(c)
                if toks[:len(pat)] == list(pat) or (len(pat) > 1 and all(p in toks for p in pat)) or toks == list(pat):
                    mapping[field] = c
                    used.add(c)
                    break
            if field in mapping:
                break
    return mapping


def _num(v) -> Optional[float]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    x = float(v)
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError("not a finite number")
    return x


def _arsenic_ppb_from_row(r: Dict[str, Any], mapping: Dict[str, str], bare_is_mg_l: bool) -> Optional[float]:
    if "arsenic_ppb" in mapping and _num(r.get(mapping["arsenic_ppb"])) is not None:
        return _num(r.get(mapping["arsenic_ppb"]))
    if "arsenic_mg_l" in mapping and _num(r.get(mapping["arsenic_mg_l"])) is not None:
        return _num(r.get(mapping["arsenic_mg_l"])) * 1000.0
    if "arsenic" in mapping and _num(r.get(mapping["arsenic"])) is not None:
        x = _num(r.get(mapping["arsenic"]))
        return x * 1000.0 if bare_is_mg_l else x
    return None


def _bare_arsenic_is_mg_l(records: List[Dict[str, Any]], mapping: Dict[str, str]) -> bool:
    if "arsenic" not in mapping:
        return False
    vals = []
    for r in records[:200]:
        try:
            x = _num(r.get(mapping["arsenic"]))
        except (TypeError, ValueError):
            continue
        if x is not None:
            vals.append(x)
    return bool(vals) and max(vals) < 2.0 and any(0 < v < 1.0 for v in vals)


def _parse_time(v) -> Optional[datetime]:
    if v in (None, ""):
        return None
    try:
        d = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


@app.post("/api/data/import/preview", response_model=schemas.DataImportPreviewResponse, tags=["Data Management"])
def preview_data_import(records: List[Dict[str, Any]]):
    """
    Preview and validate user-supplied CSV/JSON water sample records before committing.
    Detects columns by whole words, works out mg/L vs µg/L, and flags invalid values.
    """
    if not records:
        raise HTTPException(status_code=400, detail="Empty records payload submitted.")
    if len(records) > 20000:
        raise HTTPException(status_code=413, detail="Too many rows in one import (limit 20,000).")

    cols = list(dict.fromkeys(k for r in records[:200] for k in r.keys()))
    mapping = detect_columns(cols)
    errors = []
    if not any(k in mapping for k in ("arsenic_ppb", "arsenic_mg_l", "arsenic")):
        errors.append("Missing required arsenic column (e.g. 'arsenic_ppb', 'arsenic_ug_l', or 'arsenic_mg_l').")

    bare_mg = _bare_arsenic_is_mg_l(records, mapping)
    shown = dict(mapping)
    for k in ("arsenic_ppb", "arsenic_mg_l"):
        if k in mapping:
            shown.setdefault("arsenic", mapping[k])   # older clients read column_mapping["arsenic"]
    shown["arsenic_unit"] = ("mg/L" if "arsenic_mg_l" in mapping or bare_mg else "µg/L") if "arsenic" in shown else None
    for idx, r in enumerate(records[:500]):
        if errors and idx == 0 and "Missing required" in errors[0]:
            break
        try:
            as_ppb = _arsenic_ppb_from_row(r, mapping, bare_mg)
        except (ValueError, TypeError):
            errors.append(f"Row {idx+1}: arsenic value is not a number.")
            continue
        if as_ppb is None:
            errors.append(f"Row {idx+1}: arsenic value is empty.")
        elif as_ppb < 0:
            errors.append(f"Row {idx+1}: Negative arsenic concentration ({as_ppb}) is physically invalid.")
        for field, (lo, hi) in {"ph": (0, 14), "turbidity_ntu": (0, 1000), "conductivity_us_cm": (0, 50000),
                                "temperature_c": (-10, 60)}.items():
            if field in mapping:
                try:
                    x = _num(r.get(mapping[field]))
                except (ValueError, TypeError):
                    errors.append(f"Row {idx+1}: {mapping[field]} is not a number.")
                    continue
                if x is not None and not (lo <= x <= hi):
                    errors.append(f"Row {idx+1}: {mapping[field]} = {x} is outside {lo}-{hi}.")

    return schemas.DataImportPreviewResponse(
        detected_rows=len(records),
        detected_columns=cols,
        column_mapping={k: v for k, v in shown.items() if v is not None},
        preview_records=records[:5],
        validation_errors=errors[:10],
        is_valid=len(errors) == 0,
        source_type_inferred="manual_import",
    )


@app.post("/api/data/import/commit", response_model=schemas.DataImportCommitResponse, tags=["Data Management"],
          dependencies=[Depends(require_writer)])
def commit_data_import(payload: schemas.DataImportCommitRequest, db: Session = Depends(get_db)):
    """Commit validated external records with provenance and idempotency. Uses the same column detection as preview."""
    inserted = duplicates = errors = 0
    if len(payload.records) > 20000:
        raise HTTPException(status_code=413, detail="Too many rows in one import (limit 20,000).")
    device = _get_or_create_device(db, payload.device_code or "IMPORT-01")
    cols = list(dict.fromkeys(k for r in payload.records[:200] for k in r.keys()))
    mapping = detect_columns(cols)
    bare_mg = _bare_arsenic_is_mg_l(payload.records, mapping)
    source_type = payload.source_type or "manual_import"
    seen_keys = set()

    def get(r, field):
        return _num(r.get(mapping[field])) if field in mapping else None

    for r in payload.records:
        try:
            as_ppb = _arsenic_ppb_from_row(r, mapping, bare_mg)
            if as_ppb is None or as_ppb < 0:
                errors += 1
                continue
            ph, cond, turb, temp = get(r, "ph"), get(r, "conductivity_us_cm"), get(r, "turbidity_ntu"), get(r, "temperature_c")
            idemp = str(r.get(mapping["sample_id"]) if "sample_id" in mapping and r.get(mapping["sample_id"]) not in (None, "")
                        else uuid.uuid4())[:64]
            if idemp in seen_keys or db.query(models.Reading).filter_by(idempotency_key=idemp).first():
                duplicates += 1
                continue

            eval_res = classify_arsenic_neural(
                arsenic_ppb=as_ppb, ph=_val(ph, 7.2), conductivity_us_cm=_val(cond, 400.0),
                turbidity_ntu=_val(turb, 2.0), temperature_c=_val(temp, 24.0), source_type=source_type,
            )
            recorded = _parse_time(r.get(mapping["recorded_at"])) if "recorded_at" in mapping else None
            lat, lon = get(r, "latitude"), get(r, "longitude")
            rec = models.Reading(
                device_id=device.id,
                arsenic_ppb=as_ppb,
                classification=eval_res.label,
                analytical_status=eval_res.analytical_status,
                regulatory_tier=eval_res.regulatory_tier,
                is_safe_to_drink=eval_res.is_safe_to_drink,
                uncertainty_ppb=eval_res.uncertainty_ppb,
                confidence=0.90,
                source_type=source_type,
                is_simulated=source_type != "hardware",
                method_version=METHOD_NAME,
                model_version=active_model_name(),
                idempotency_key=idemp,
                ph=ph,
                temperature_c=temp,
                conductivity_us_cm=cond,
                turbidity_ntu=turb,
                latitude=lat if lat is not None and -90 <= lat <= 90 else None,
                longitude=lon if lon is not None and -180 <= lon <= 180 else None,
                source_label=str(r.get(mapping["source_label"]))[:64] if "source_label" in mapping and r.get(mapping["source_label"]) else "Imported Dataset",
                recorded_at=recorded or now_utc(),
                received_at=now_utc(),
            )
            db.add(rec)
            seen_keys.add(idemp)
            inserted += 1
        except Exception:
            errors += 1

    db.commit()
    return schemas.DataImportCommitResponse(
        inserted_count=inserted,
        duplicate_count=duplicates,
        error_count=errors,
        status="success" if inserted > 0 else "no_records_inserted",
        message=f"Import completed: {inserted} records added, {duplicates} duplicates skipped, {errors} errors.",
    )


@app.get("/api/data/export", tags=["Data Management"])
def export_data(
    format: str = Query("json", description="Export format: json | csv"),
    redact_coordinates: bool = Query(False, description="Redact exact coordinates for public privacy"),
    source_type: Optional[str] = Query(None),
    device_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Export water quality readings with schema version and lineage, as JSON or CSV (spreadsheet-safe)."""
    if format not in ("json", "csv"):
        raise HTTPException(status_code=422, detail="format must be json or csv.")
    q = db.query(models.Reading).order_by(models.Reading.recorded_at.desc())
    if source_type:
        q = q.filter(models.Reading.source_type == source_type)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    readings = q.all()

    records = []
    for r in readings:
        lat = None if redact_coordinates else r.latitude
        lon = None if redact_coordinates else r.longitude
        records.append({
            "id": r.id,
            "sample_id": r.idempotency_key or f"SAMPLE-{r.id:06d}",
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            "arsenic_ppb": r.arsenic_ppb,
            "arsenic_mg_l": round(r.arsenic_ppb / 1000.0, 4),
            "unit": "µg/L (ppb)",
            "classification": r.classification,
            "analytical_status": r.analytical_status,
            "regulatory_tier": r.regulatory_tier,
            "is_safe_to_drink": r.is_safe_to_drink,
            "source_type": r.source_type,
            "is_simulated": r.is_simulated,
            "method_version": r.method_version,
            "model_version": r.model_version,
            "ph": r.ph,
            "conductivity_us_cm": r.conductivity_us_cm,
            "turbidity_ntu": r.turbidity_ntu,
            "temperature_c": r.temperature_c,
            "latitude": lat,
            "longitude": lon,
            "coordinates_redacted": redact_coordinates,
        })

    if format == "csv":
        cols = ["sample_id", "recorded_at", "device_code", "arsenic_ppb", "arsenic_mg_l", "classification",
                "regulatory_tier", "is_safe_to_drink", "ph", "conductivity_us_cm", "turbidity_ntu", "temperature_c",
                "latitude", "longitude", "source_type", "is_simulated", "model_version", "method_version"]
        codes = {d.id: d.device_code for d in db.query(models.Device).all()}

        def cell(v):
            v = "" if v is None else str(v)
            # spreadsheet formula injection: a cell starting with = + - @ would run as a formula
            return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") and not _is_number(v) else v

        def rows():
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(cols)
            for rec, r in zip(records, readings):
                rec = dict(rec, device_code=codes.get(r.device_id))
                w.writerow([cell(rec.get(c)) for c in cols])
                if buf.tell() > 32768:
                    yield buf.getvalue(); buf.seek(0); buf.truncate()
            yield buf.getvalue()

        fname = f"aquasentry_readings_{now_utc().strftime('%Y%m%d')}.csv"
        return StreamingResponse(rows(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    return {
        "export_metadata": {
            "schema_version": "1.3.0",
            "exported_at": now_utc().isoformat(),
            "records_count": len(records),
            "source_type_filter": source_type,
            "coordinates_redacted": redact_coordinates,
            "regulatory_framework": "WHO GDWQ 4th Ed / BIS 10500:2012",
            "disclaimer": "Autonomous field screening indicators. Certified laboratory testing required for potability certification.",
        },
        "records": records,
    }


# ---------------------------------------------------------------------------
# Demo Data Management (Opt-In Synthetic Data)
# ---------------------------------------------------------------------------

@app.post("/api/demo/load", tags=["Demo Management"], dependencies=[Depends(require_writer)])
def load_demo_data(db: Session = Depends(get_db)):
    """
    Opt-in demo dataset loader: inserts 5 realistic benchmark profiles
    explicitly marked as SYNTHETIC DEMO with full provenance.
    """
    demo_profiles = [
        {"as_ppb": 6.5, "ph": 7.42, "ec": 380.0, "turb": 1.2, "temp": 23.5, "label": "Demo Well 1 (Below LOD)"},
        {"as_ppb": 25.0, "ph": 7.18, "ec": 450.0, "turb": 2.8, "temp": 24.1, "label": "Demo Well 2 (LOD-LOQ Range)"},
        {"as_ppb": 42.0, "ph": 6.85, "ec": 510.0, "turb": 3.4, "temp": 24.8, "label": "Demo TubeWell 3 (Exceeds WHO)"},
        {"as_ppb": 85.0, "ph": 6.60, "ec": 680.0, "turb": 5.2, "temp": 25.2, "label": "Demo Canal 4 (Exceeds BIS Unsafe)"},
        {"as_ppb": 210.0, "ph": 6.40, "ec": 890.0, "turb": 7.8, "temp": 26.0, "label": "Demo Hotspot 5 (Acute Hazardous)"},
    ]

    device = _get_or_create_device(db, "DEMO-BOT-01")
    added = 0
    for p in demo_profiles:
        eval_res = classify_arsenic_neural(
            arsenic_ppb=p["as_ppb"],
            ph=p["ph"],
            conductivity_us_cm=p["ec"],
            turbidity_ntu=p["turb"],
            temperature_c=p["temp"],
            source_type="synthetic_demo",
        )
        rec = models.Reading(
            device_id=device.id,
            arsenic_ppb=p["as_ppb"],
            classification=eval_res.label,
            analytical_status=eval_res.analytical_status,
            regulatory_tier=eval_res.regulatory_tier,
            is_safe_to_drink=eval_res.is_safe_to_drink,
            uncertainty_ppb=eval_res.uncertainty_ppb,
            confidence=0.98,
            source_type="synthetic_demo",
            is_simulated=True,
            method_version=METHOD_NAME,
            model_version=active_model_name(),
            idempotency_key=f"DEMO-{p['as_ppb']}-{uuid.uuid4().hex[:6]}",
            ph=p["ph"],
            temperature_c=p["temp"],
            conductivity_us_cm=p["ec"],
            turbidity_ntu=p["turb"],
            latitude=18.5204 + (added * 0.005),
            longitude=73.8567 + (added * 0.005),
            source_label=p["label"],
            recorded_at=now_utc() - timedelta(minutes=(5 - added) * 10),
            received_at=now_utc(),
        )
        db.add(rec)
        added += 1

    db.commit()
    return {
        "status": "success",
        "loaded_records": added,
        "message": "Demo benchmark profiles loaded. All records are clearly marked DEMO / SIMULATED.",
    }


# ---------------------------------------------------------------------------
# AquaNet-V1 Neural Network Inference Endpoints (GET & POST)
# ---------------------------------------------------------------------------

class NeuralInferencePayload(schemas.BaseModel):
    arsenic_concentration_mg_l: Optional[float] = None
    arsenic_mg_l: Optional[float] = None
    arsenic_ppb: Optional[float] = None
    ph: Optional[float] = 7.35
    conductivity_us_cm: Optional[float] = 412.0
    turbidity_ntu: Optional[float] = 2.1
    temperature_c: Optional[float] = 24.2


@app.post("/api/neural/inference", response_model=schemas.NeuralInferenceResponse, tags=["Neural Network"])
def run_neural_inference_post(payload: NeuralInferencePayload):
    """Run forward-pass inference on the AquaNet-V1 multimodal deep neural network via POST."""
    as_mg = payload.arsenic_mg_l if payload.arsenic_mg_l is not None else payload.arsenic_concentration_mg_l
    if as_mg is None and payload.arsenic_ppb is not None:
        as_mg = payload.arsenic_ppb / 1000.0
    if as_mg is None:
        as_mg = 0.018

    res = forward_pass(
        arsenic_mg_l=as_mg,
        ph=payload.ph if payload.ph is not None else 7.35,
        conductivity_us_cm=payload.conductivity_us_cm if payload.conductivity_us_cm is not None else 412.0,
        turbidity_ntu=payload.turbidity_ntu if payload.turbidity_ntu is not None else 2.1,
        temperature_c=payload.temperature_c if payload.temperature_c is not None else 24.2,
    )
    return schemas.NeuralInferenceResponse(**res)


@app.get("/api/neural/v3", tags=["Neural Network"])
def run_neural_v3(
    arsenic_mg_l: float = Query(0.018, ge=0.0, le=2.0, description="Arsenic concentration in mg/L"),
    ph: float = Query(7.35, ge=4.0, le=11.0),
    conductivity_us_cm: float = Query(412.0, ge=0.0, le=10000.0),
    turbidity_ntu: float = Query(2.1, ge=0.0, le=100.0),
    temperature_c: float = Query(24.2, ge=0.0, le=50.0),
):
    """AquaNet-V3 (the trained model used for stored readings): network vote, final verdict after the safety rules,
    probabilities, entropy and the reasons any rule applied."""
    from .aquanet_v3 import predict
    return predict(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c)


@app.get("/api/neural/inference", response_model=schemas.NeuralInferenceResponse, tags=["Neural Network"])
def run_neural_inference_get(
    arsenic_mg_l: float = Query(0.018, ge=0.0, le=2.0, description="Arsenic concentration in mg/L"),
    ph: float = Query(7.35, ge=4.0, le=11.0, description="Water pH"),
    conductivity_us_cm: float = Query(412.0, ge=0.0, le=10000.0, description="Conductivity in µS/cm"),
    turbidity_ntu: float = Query(2.1, ge=0.0, le=100.0, description="Turbidity in NTU"),
    temperature_c: float = Query(24.2, ge=0.0, le=50.0, description="Water temperature in °C"),
):
    """Run forward-pass inference on the AquaNet-V1 multimodal deep neural network via GET query params."""
    res = forward_pass(
        arsenic_mg_l=arsenic_mg_l,
        ph=ph,
        conductivity_us_cm=conductivity_us_cm,
        turbidity_ntu=turbidity_ntu,
        temperature_c=temperature_c,
    )
    return schemas.NeuralInferenceResponse(**res)


# ---------------------------------------------------------------------------
# AI Chatbot Agent Integration (Google Gemini 3.6 Flash) with Domain Intent Gate
# ---------------------------------------------------------------------------

from google import genai
from google.genai import types

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = None
if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
    try:
        client = genai.Client(api_key=gemini_api_key)
    except Exception as e:
        print(f"Notice: Gemini client init error: {e}")
        client = None

BASE_SYSTEM_PROMPT = """You are the official AquaSentry Scientific AI Assistant. Use the following project knowledge to answer questions accurately and honestly.

CORE ETHICAL & PUBLIC HEALTH RULE:
AquaSentry is an autonomous screening and surveillance prototype. It is NOT an ISO 17025 accredited laboratory instrument. You must NEVER declare water safe for drinking without advising accredited laboratory confirmation (such as ICP-MS or HG-AAS).

Analytical Chemistry & Detection Limits:
- Sensing Mechanism: Anodic Stripping Voltammetry (ASV) on screen-printed carbon electrodes (MAS-G1 strip As-M003050) sampled via ADS1115 16-bit ADC at -800 mV peak potential.
- Limit of Detection (LOD): 20.0 µg/L (0.020 mg/L).
- Limit of Quantification (LOQ): 30.0 µg/L (0.030 mg/L).
- Validated Calibration Range: 30.0 to 500.0 µg/L (0.030 to 0.500 mg/L).
- Regulatory Standards:
  * WHO Provisional Drinking Water Guideline: 10.0 µg/L (0.010 mg/L).
  * India IS 10500:2012: 10.0 µg/L acceptable AND permissible. Amendment No. 1 (2015) removed the old 50 µg/L
    "absence of alternate source" relaxation, so 10 µg/L is the only limit. Never describe 10-50 µg/L as permissible.
- CRITICAL SCIENTIFIC FACT: Because the sensor's LOD (20 µg/L) is higher than the 10 µg/L limit, readings below 20 µg/L CANNOT confirm the water is safe, and ANY arsenic the sensor detects (>= 20 µg/L) already exceeds both the WHO and Indian limits. Always explain this transparently.

Multi-Contaminant Sensing Policy:
- The current AquaSentry physical robot ONLY has an ASV sensor for Arsenic (As).
- Lead, Cadmium, Mercury, Chromium, Fluoride, and Nitrate are cataloged capabilities but require dedicated sensor modules or external laboratory testing. Never claim the single arsenic strip detects all metals simultaneously.

Neural Network (AquaNet-V3, used for stored readings and on the ESP32):
- 5-16-12-4 multilayer perceptron, 352 parameters (about 1.4 KB as float32), trained on simulated readings with
  realistic sensor noise. Inputs: arsenic (log10), pH, conductivity, turbidity, temperature. Outputs: Safe, Caution, Unsafe, Hazardous.
- Fixed safety rules run after the network and can only make the verdict stricter: arsenic >= 20 µg/L (detected)
  is at least Unsafe, > 150 µg/L is Hazardous, 10-20 µg/L is Caution (unconfirmed, lab test). pH, turbidity and
  conductivity limits also apply.
- AquaNet-V1 (5-8-6-4, 112 hand-set weights) is the original, kept for comparison.
- All accuracy figures are from simulated data; the model has not been validated on real field samples.

Robot Hardware Specs:
- Twin-hull catamaran (1.05m x 0.62m, 11.4kg displacement).
- Solar 6V/5W + 18650 Li-ion 3000mAh buffer; 6-hour duty cycle consuming 0.6-1.0 Wh/day.
- Non-immersion microfluidic sampling: 15 mL peristaltic pump chamber protects sensors from open-water biofilm fouling.
- Communications: LoRa (2 km+) + HC-05 Bluetooth + GPS geotagging.
"""


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["AI Chat"])
def chat(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """
    Intelligent chatbot endpoint with server-side intent classification,
    grounded database context, and public health guardrails.
    """
    # 1. Server-side Intent Gate & Prompt Injection Filter
    intent, preformatted = classify_user_prompt(request.message)
    if preformatted:
        return schemas.ChatResponse(reply=preformatted, intent=intent.value, grounded=False)

    # 2. Ground every answer in the database: the latest reading and each node's status and trend
    latest_rec = db.query(models.Reading).order_by(models.Reading.recorded_at.desc()).first()
    latest_dict = None
    if latest_rec:
        latest_dict = {
            "arsenic_ppb": latest_rec.arsenic_ppb,
            "arsenic_mg_l": round(latest_rec.arsenic_ppb / 1000.0, 4),
            "analytical_status": latest_rec.analytical_status,
            "regulatory_tier": latest_rec.regulatory_tier,
            "source_type": latest_rec.source_type,
            "recorded_at": _utc(latest_rec.recorded_at).isoformat() if latest_rec.recorded_at else "Just now",
            "is_safe_to_drink": latest_rec.is_safe_to_drink,
            "device_code": latest_rec.device.device_code if latest_rec.device is not None else None,
        }
    counts, unsafe = _counts(db)
    fleet = [_device_out(db, d, counts, unsafe).model_dump(mode="json") for d in db.query(models.Device).all()]
    fleet.sort(key=lambda d: (not d["is_hardware"], d["device_code"]))

    if not client:
        # No LLM (no key, or a field laptop without internet): answer from the data with fixed wording.
        return schemas.ChatResponse(reply=offline_answer(request.message, latest_dict, fleet),
                                    intent="in_scope", grounded=True)

    grounded_context = format_grounded_context(latest_dict) + format_fleet_context(fleet)
    dynamic_prompt = BASE_SYSTEM_PROMPT + "\n" + grounded_context

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=request.message,
            config=types.GenerateContentConfig(
                system_instruction=dynamic_prompt,
                temperature=0.2,
            ),
        )
        return schemas.ChatResponse(reply=response.text or "(no answer returned)", intent="in_scope", grounded=True)
    except Exception as e:
        # No internet, quota, or a retired model: still answer from the data instead of only apologising.
        error_str = str(e)
        print(f"[chat] Gemini error: {error_str}")
        if "503" in error_str or "high demand" in error_str:
            why = "Google's AI servers are busy right now, so this is the offline answer."
        elif any(k in error_str for k in ("401", "403", "404", "API key", "not found")):
            why = "The AI assistant could not answer (check GEMINI_API_KEY and GEMINI_MODEL in .env), so this is the offline answer."
        else:
            why = "The AI assistant could not be reached, so this is the offline answer."
        return schemas.ChatResponse(reply=f"⚠️ *{why}*\n\n" + offline_answer(request.message, latest_dict, fleet),
                                    intent="in_scope", grounded=True)


# ===========================================================================
# Imp 19: WebSocket Real-Time Voltammetry Streaming Endpoint
# ===========================================================================

@app.websocket("/ws/voltammetry")
async def websocket_voltammetry_stream(websocket: WebSocket):
    """
    Real-time bidirectional WebSocket streaming endpoint for ASV voltammogram curves.
    Streams incremental potential and current data packets directly to connected dashboards.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                await websocket.send_json({"type": "error", "message": "Send a JSON object."})
                continue
            cmd = data.get("command", "start_sweep")
            try:
                as_conc = float(data.get("arsenic_mg_l", 0.035))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "message": "arsenic_mg_l must be a number."})
                continue
            if not (0.0 <= as_conc <= 1.0) or as_conc != as_conc:
                await websocket.send_json({"type": "error", "message": "arsenic_mg_l must be between 0 and 1."})
                continue

            if cmd in ("start_sweep", "simulate"):
                potentials, currents = generate_synthetic_asv_trace(as_conc * 1000.0)  # function expects µg/L
                total = len(potentials)

                for idx in range(total):
                    pct = round(((idx + 1) / total) * 100, 1)
                    await websocket.send_json({
                        "type": "sweep_point",
                        "index": idx,
                        "total": total,
                        "potential_mv": potentials[idx],
                        "current_ua": currents[idx],
                        "progress_pct": pct,
                    })
                    await asyncio.sleep(0.01)

                processed = process_voltammetry_trace(potentials, currents)
                await websocket.send_json({
                    "type": "sweep_complete",
                    "estimated_arsenic_mg_l": processed.estimated_arsenic_mg_l,
                    "net_peak_current_ua": processed.peak.net_peak_height_ua if processed.peak else 0.0,
                    "peak_potential_mv": processed.peak.peak_potential_mv if processed.peak else -800.0,
                    "qc_status": processed.qc_status.value if hasattr(processed.qc_status, "value") else str(processed.qc_status),
                })
            else:
                await websocket.send_json({"type": "pong", "message": "AquaSentry Voltammetry Stream Active"})
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()


# ===========================================================================
# Imp 20: Screening Report PDF Endpoint
# ===========================================================================

@app.get("/api/reports/certificate/pdf", tags=["Reports"])
def download_potability_certificate(
    reading_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Download a one-page PDF screening report for a stored reading (the latest one if no id is given).
    Returns 404 if there is no such reading: the report never invents values.
    """
    if reading_id is not None:
        rec = db.query(models.Reading).filter_by(id=reading_id).first()
    else:
        rec = db.query(models.Reading).order_by(models.Reading.recorded_at.desc()).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="No reading found. Record or load a reading before downloading a report.")

    data = {
        "reading_id": rec.id,
        "device_code": rec.device.device_code if getattr(rec, "device", None) is not None else None,
        "recorded_at": rec.recorded_at.strftime("%Y-%m-%d %H:%M:%S UTC") if rec.recorded_at else "Unknown",
        "source_type": rec.source_type or "unknown",
        "arsenic_mg_l": rec.arsenic_ppb / 1000.0,
        "ph": rec.ph,
        "turbidity_ntu": rec.turbidity_ntu,
        "conductivity_us_cm": rec.conductivity_us_cm,
        "temperature_c": rec.temperature_c,
        "predicted_class": rec.classification,
        "model_version": rec.model_version or active_model_name(),
    }
    # Model confidence is recomputed from the stored values with the model that classified the reading.
    try:
        args = dict(arsenic_mg_l=data["arsenic_mg_l"], ph=_val(rec.ph, 7.2),
                    conductivity_us_cm=_val(rec.conductivity_us_cm, 400.0),
                    turbidity_ntu=_val(rec.turbidity_ntu, 2.0), temperature_c=_val(rec.temperature_c, 24.0))
        if (rec.model_version or "").upper().endswith("V1"):
            nn = forward_pass(**args)
        else:
            from .aquanet_v3 import predict as _v3_predict
            nn = _v3_predict(args["arsenic_mg_l"], args["ph"], args["conductivity_us_cm"], args["turbidity_ntu"], args["temperature_c"])
        data["model_confidence_pct"] = nn["confidence_pct"]
        data["model_entropy"] = nn["entropy"]
    except Exception:
        pass

    pdf_bytes = generate_potability_certificate_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=AquaSentry_Screening_Report_{rec.id}.pdf"},
    )


# ===========================================================================
# Imp 21: Emergency Alert Cache Endpoint
# ===========================================================================

@app.get("/api/alerts/recent", tags=["Alerts"])
def get_recent_alerts(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Recent Unsafe / Hazardous readings as alerts. Built from the database, so they survive a server restart."""
    rows = (db.query(models.Reading)
            .filter(models.Reading.classification.in_(["Unsafe", "Hazardous"]))
            .order_by(models.Reading.recorded_at.desc()).limit(limit).all())
    alerts = []
    for r in rows:
        a = build_alert(r.classification, r.arsenic_ppb, reading_id=r.id, source_type=r.source_type,
                        source_label=r.source_label,
                        device_code=r.device.device_code if getattr(r, "device", None) is not None else None)
        if a:
            ts = r.recorded_at if r.recorded_at.tzinfo else r.recorded_at.replace(tzinfo=timezone.utc)
            a["id"], a["timestamp"] = f"reading-{r.id}", ts.isoformat()
            alerts.append(a)
    # Early warnings that are not single readings: a rising trend, or a node that stopped reporting.
    counts, unsafe = _counts(db)
    for d in db.query(models.Device).all():
        info = _device_out(db, d, counts, unsafe)
        if not info.is_hardware:
            continue
        if info.trend and info.trend.direction == "rising":
            alerts.append({"id": f"trend-{d.device_code}", "type": "trend", "level": "NOTICE", "device_code": d.device_code,
                           "timestamp": now_utc().isoformat(), "message": f"{d.device_code}: {info.trend.message}",
                           "action_required": "Test this source more often and arrange a laboratory test."})
        batt = info.latest.battery_pct if info.latest else None
        if batt is not None and batt <= LOW_BATTERY_PCT:
            alerts.append({"id": f"battery-{d.device_code}", "type": "battery", "level": "NOTICE", "device_code": d.device_code,
                           "timestamp": now_utc().isoformat(), "message": f"{d.device_code} battery is at {batt:.0f}%.",
                           "action_required": "Charge or replace the battery before the node stops testing."})
        if info.status == "offline":
            hrs = (info.minutes_since_seen or 0) / 60
            alerts.append({"id": f"offline-{d.device_code}", "type": "offline", "level": "NOTICE", "device_code": d.device_code,
                           "timestamp": now_utc().isoformat(), "message": f"{d.device_code} has not reported for {hrs:.0f} hours.",
                           "action_required": "Check power, Wi-Fi and the status page of the node."})
    return {"count": len(alerts), "alerts": alerts}


# ===========================================================================
# Imp 22: SQLite WAL Compaction Endpoint
# ===========================================================================

@app.post("/api/admin/backup", tags=["Admin"], dependencies=[Depends(require_admin)])
def backup_now():
    """Consistent copy of the SQLite database into AquaSentry_Platform/backups/ (safe while running)."""
    dest = os.getenv("AQUASENTRY_BACKUP_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups"))
    return backup_database(dest)


@app.post("/api/admin/db/compact", tags=["Admin"], dependencies=[Depends(require_admin)])
def compact_sqlite_database():
    """Imp 22: Execute SQLite WAL checkpointing, PRAGMA optimize, and report file stats."""
    return compact_database()


# ===========================================================================
# Dashboard: serve frontend/ at "/" so http://localhost:8000 opens the UI.
# Mounted last, so every /api and /ws route above still takes priority.
# ===========================================================================

from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles

_FRONTEND_DIR = _Path(os.getenv("AQUASENTRY_FRONTEND_DIR", _Path(__file__).resolve().parent.parent / "frontend"))
if _FRONTEND_DIR.is_dir():
    app.mount("/", _StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
