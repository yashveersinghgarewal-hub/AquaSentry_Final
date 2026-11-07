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
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db, Base, ensure_sqlite_columns, compact_database
from .classification import classify_arsenic_neural
from .standards import (
    WHO_GUIDELINE_UG_L,
    BIS_PERMISSIBLE_LIMIT_UG_L,
    LOD_UG_L,
    LOQ_UG_L,
    METHOD_NAME,
    CALIBRATION_SLOPE,
    CALIBRATION_INTERCEPT,
    mg_l_to_ug_l,
    ug_l_to_mg_l,
)
from .neural_classifier import forward_pass, NODES_COUNT, SYNAPSES_COUNT
from .analytes import (
    ANALYTE_REGISTRY,
    get_analyte_profile,
    list_supported_analytes,
    evaluate_analyte_concentration,
)
from .signal_processing import (
    process_voltammetry_trace,
    generate_synthetic_asv_trace,
)
from .chat_policy import (
    ChatIntent,
    classify_user_prompt,
    format_grounded_context,
)

# Create tables on startup and apply non-destructive column migrations
Base.metadata.create_all(bind=engine)
ensure_sqlite_columns()

app = FastAPI(
    title="AquaSentry Water Safety & Surveillance API",
    description="Scientific backend and edge neural classifier for autonomous water quality monitoring.",
    version="1.3.0",
)

cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "model_version": "AquaNet-V1",
        "neural_model": f"AquaNet-V1 ({SYNAPSES_COUNT} synapses)",
        "neural_nodes": NODES_COUNT,
        "neural_synapses": SYNAPSES_COUNT,
        "standards_version": "WHO-2017 / BIS-10500:2012 / EPA-2021",
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

def dispatch_emergency_alert(data: Dict[str, Any]):
    as_ppb = data.get("arsenic_ppb", 0.0)
    as_ppm = data.get("arsenic_ppm", as_ppb / 1000.0)
    if as_ppb >= 50.0:  # Exceeds BIS 10500 limit (50 ug/L)
        alert = {
            "id": str(uuid.uuid4()),
            "timestamp": now_utc().isoformat(),
            "level": "CRITICAL" if as_ppb >= 150.0 else "WARNING",
            "contaminant": "Total Arsenic (As)",
            "arsenic_ppb": round(as_ppb, 1),
            "arsenic_mg_l": round(as_ppm, 4),
            "source_type": data.get("source_type", "tank_sentry"),
            "message": f"CRITICAL ARSENIC EXCEEDANCE: {as_ppb:.1f} µg/L detected (BIS limit: 50.0 µg/L, WHO: 10.0 µg/L)",
            "action_required": "Do NOT drink. Switch to alternative potable source immediately.",
        }
        RECENT_EMERGENCY_ALERTS.append(alert)
        if len(RECENT_EMERGENCY_ALERTS) > 50:
            RECENT_EMERGENCY_ALERTS.pop(0)

        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if webhook_url:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(alert).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=2.0)
            except Exception as e:
                print(f"Warning: Webhook dispatch error: {e}")


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
         Paragraph("<b>Method:</b> Anodic stripping voltammetry (MAS-G1) + AquaNet-V1 screening model", body_style)],
        [Paragraph(f"<b>Device:</b> {reading_dict.get('device_code', 'Unknown')}", body_style),
         Paragraph("<b>Reference limits:</b> WHO GDWQ 4th ed. / BIS IS 10500:2012", body_style)],
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
        model_line = (f"<br/><font size=8 color='#4B5D58'>AquaNet-V1 model confidence: {reading_dict['model_confidence_pct']:.1f}% | "
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
        as_status = "Below sensor LOD: lab test needed"
    elif as_ug_l <= BIS_PERMISSIBLE_LIMIT_UG_L:
        as_status = "Above WHO, within BIS permissible"
    elif as_ug_l <= 150.0:
        as_status = "Exceeds BIS: unsafe"
    else:
        as_status = "Hazardous (above 150 µg/L)"

    def status(val, ok):
        return "Not measured" if val is None else ("Within limit" if ok(val) else "Outside limit")

    chem_data = [
        ["Parameter", "Measured value", "Limit used", "Status"],
        ["Total arsenic (As)", f"{as_ug_l:.1f} µg/L ({as_mg_l:.4f} mg/L)", "WHO 10 µg/L; BIS 50 µg/L", as_status],
        ["pH", _fmt_or_missing(ph_val, ".2f"), "6.5 - 8.5 (BIS)", status(ph_val, lambda v: 6.5 <= v <= 8.5)],
        ["Turbidity", _fmt_or_missing(turb_val, ".2f", "NTU"), "5 NTU (BIS permissible)", status(turb_val, lambda v: v <= 5.0)],
        ["Conductivity", _fmt_or_missing(ec_val, ".0f", "µS/cm"), "1500 µS/cm (AquaSentry screening)", status(ec_val, lambda v: v <= 1500)],
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
                  f"(slope {CALIBRATION_SLOPE} µA per mg/L, intercept {CALIBRATION_INTERCEPT} µA), then classified by AquaNet-V1 "
                  "with fixed WHO/BIS safety rules applied after the model.", body_style),
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

def _get_or_create_device(db: Session, device_code: str) -> models.Device:
    device = db.query(models.Device).filter_by(device_code=device_code).first()
    ts = now_utc()
    if device is None:
        device = models.Device(
            device_code=device_code,
            first_seen=ts,
            last_seen=ts,
            status="online",
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = ts
        db.commit()
    return device


# ---------------------------------------------------------------------------
# Readings: Ingest (Called by Arduino / LoRa / Bluetooth Bridge)
# ---------------------------------------------------------------------------

@app.post("/api/readings", response_model=schemas.ReadingResponse, tags=["Readings"])
def create_reading(payload: schemas.ReadingCreate, db: Session = Depends(get_db)):
    """
    Ingest a new arsenic reading from the autonomous vessel or simulator.
    Evaluates risk with conservative public health precedence rules and stores full audit lineage.
    """
    # Idempotency check: if an idempotency key was supplied and already exists, return existing reading
    if payload.idempotency_key:
        existing = db.query(models.Reading).filter_by(idempotency_key=payload.idempotency_key).first()
        if existing:
            eval_res = classify_arsenic_neural(
                arsenic_ppb=existing.arsenic_ppb,
                ph=existing.ph or 7.2,
                conductivity_us_cm=existing.conductivity_us_cm or 400.0,
                turbidity_ntu=existing.turbidity_ntu or 2.0,
                temperature_c=existing.temperature_c or 24.0,
                source_type=existing.source_type or "simulated",
            )
            return schemas.ReadingResponse(
                reading=schemas.ReadingOut.model_validate(existing),
                label=eval_res.label,
                severity=eval_res.severity,
                message=f"[Idempotent Cache Hit] {eval_res.message}",
                action=eval_res.action,
                analytical_status=eval_res.analytical_status,
                regulatory_tier=eval_res.regulatory_tier,
                is_safe_to_drink=eval_res.is_safe_to_drink,
                uncertainty_ppb=eval_res.uncertainty_ppb,
                is_simulated=existing.is_simulated,
                disclaimer=eval_res.disclaimer,
            )

    try:
        eval_res = classify_arsenic_neural(
            arsenic_ppb=payload.arsenic_ppb,
            ph=payload.ph or 7.2,
            conductivity_us_cm=payload.conductivity_us_cm or 400.0,
            turbidity_ntu=payload.turbidity_ntu or 2.0,
            temperature_c=payload.temperature_c or 24.0,
            source_type=payload.source_type or "simulated",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    device = _get_or_create_device(db, payload.device_code)
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
        confidence=payload.confidence or 0.95,
        source_type=payload.source_type or "simulated",
        is_simulated=is_sim,
        method_version=METHOD_NAME,
        model_version="AquaNet-V1" if os.getenv("AQUANET_MODEL", "v3").lower() == "v1" else "AquaNet-V3",
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

    # Imp 21: Dispatch emergency exceedance alerts if arsenic exceeds safe standards
    dispatch_emergency_alert({
        "arsenic_ppb": reading.arsenic_ppb,
        "arsenic_ppm": reading.arsenic_ppb / 1000.0,
        "source_type": reading.source_type,
        "source_label": reading.source_label,
        "classification": eval_res.label,
    })

    return schemas.ReadingResponse(
        reading=schemas.ReadingOut.model_validate(reading),
        label=eval_res.label,
        severity=eval_res.severity,
        message=eval_res.message,
        action=eval_res.action,
        analytical_status=eval_res.analytical_status,
        regulatory_tier=eval_res.regulatory_tier,
        is_safe_to_drink=eval_res.is_safe_to_drink,
        uncertainty_ppb=eval_res.uncertainty_ppb,
        is_simulated=is_sim,
        disclaimer=eval_res.disclaimer,
    )


# ---------------------------------------------------------------------------
# Readings: Query & Historical Search
# ---------------------------------------------------------------------------

@app.get("/api/readings", response_model=List[schemas.ReadingOut], tags=["Readings"])
def list_readings(
    device_code: Optional[str] = Query(None, description="Filter by device code"),
    classification: Optional[str] = Query(None, description="Filter by classification tier"),
    source_type: Optional[str] = Query(None, description="Filter by source_type (simulated | hardware | manual_import)"),
    is_simulated: Optional[bool] = Query(None, description="Filter by simulated vs live"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(models.Reading)
    if device_code:
        q = q.join(models.Device).filter(models.Device.device_code == device_code)
    if classification:
        q = q.filter(models.Reading.classification == classification)
    if source_type:
        q = q.filter(models.Reading.source_type == source_type)
    if is_simulated is not None:
        q = q.filter(models.Reading.is_simulated == is_simulated)

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
        cutoff = now_utc() - timedelta(hours=24)
        # Note: reading.recorded_at may be naive datetime in SQLite; convert or compare safely
        rec_time = reading.recorded_at
        if rec_time.tzinfo is None:
            rec_time = rec_time.replace(tzinfo=timezone.utc)
        confirmed_count = (
            db.query(models.Reading.device_id)
            .filter(
                models.Reading.classification.in_(["Unsafe", "Hazardous"]),
                models.Reading.recorded_at >= (now_utc() - timedelta(hours=24)),
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
        detectedAt=reading.recorded_at.strftime("%H:%M"),
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
        synapses_count=112,
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
        raise HTTPException(status_code=422, detail=str(e))

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

@app.post("/api/data/import/preview", response_model=schemas.DataImportPreviewResponse, tags=["Data Management"])
def preview_data_import(records: List[Dict[str, Any]]):
    """
    Preview and validate user-supplied CSV/JSON water sample records before committing.
    Infers columns, checks units, flags invalid ranges, and prevents silent bad data.
    """
    if not records:
        raise HTTPException(status_code=400, detail="Empty records payload submitted.")

    first_row = records[0]
    cols = list(first_row.keys())

    mapping = {}
    errors = []
    # Column mapping detection
    for c in cols:
        cl = c.lower().strip()
        if "as" in cl or "arsenic" in cl or "ppb" in cl or "ug_l" in cl:
            mapping["arsenic"] = c
        elif "ph" in cl:
            mapping["ph"] = c
        elif "temp" in cl:
            mapping["temperature"] = c
        elif "cond" in cl or "ec" in cl:
            mapping["conductivity"] = c
        elif "turb" in cl:
            mapping["turbidity"] = c
        elif "lat" in cl:
            mapping["latitude"] = c
        elif "lon" in cl or "lng" in cl:
            mapping["longitude"] = c

    if "arsenic" not in mapping:
        errors.append("Missing required arsenic column (e.g. 'arsenic_ppb', 'arsenic_ug_l', or 'arsenic_mg_l').")

    valid_count = 0
    preview_slice = records[:5]
    for idx, r in enumerate(records[:50]):
        if "arsenic" in mapping:
            val = r.get(mapping["arsenic"])
            try:
                num = float(val)
                if num < 0:
                    errors.append(f"Row {idx+1}: Negative arsenic concentration ({num}) is physically invalid.")
                else:
                    valid_count += 1
            except (ValueError, TypeError):
                errors.append(f"Row {idx+1}: Non-numeric arsenic concentration value '{val}'.")

    return schemas.DataImportPreviewResponse(
        detected_rows=len(records),
        detected_columns=cols,
        column_mapping=mapping,
        preview_records=preview_slice,
        validation_errors=errors[:10],
        is_valid=len(errors) == 0,
        source_type_inferred="manual_import",
    )


@app.post("/api/data/import/commit", response_model=schemas.DataImportCommitResponse, tags=["Data Management"])
def commit_data_import(payload: schemas.DataImportCommitRequest, db: Session = Depends(get_db)):
    """Commit validated external records to database with strict provenance and idempotency."""
    inserted = 0
    duplicates = 0
    errors = 0

    device = _get_or_create_device(db, payload.device_code or "IMPORT-01")

    for r in payload.records:
        try:
            # Extract values with flexible column names
            as_val = (
                r.get("arsenic_ppb")
                or r.get("arsenic_ug_l")
                or r.get("arsenic")
                or (float(r.get("arsenic_mg_l", 0)) * 1000.0 if "arsenic_mg_l" in r else None)
            )
            if as_val is None:
                errors += 1
                continue

            as_ppb = float(as_val)
            ph = float(r.get("ph", 7.2)) if r.get("ph") is not None else 7.2
            cond = float(r.get("conductivity_us_cm", 400.0)) if r.get("conductivity_us_cm") is not None else 400.0
            turb = float(r.get("turbidity_ntu", 2.0)) if r.get("turbidity_ntu") is not None else 2.0
            temp = float(r.get("temperature_c", 24.0)) if r.get("temperature_c") is not None else 24.0

            idemp = r.get("idempotency_key") or r.get("sample_id") or str(uuid.uuid4())
            if db.query(models.Reading).filter_by(idempotency_key=idemp).first():
                duplicates += 1
                continue

            eval_res = classify_arsenic_neural(
                arsenic_ppb=as_ppb,
                ph=ph,
                conductivity_us_cm=cond,
                turbidity_ntu=turb,
                temperature_c=temp,
                source_type=payload.source_type or "manual_import",
            )

            rec = models.Reading(
                device_id=device.id,
                arsenic_ppb=as_ppb,
                classification=eval_res.label,
                analytical_status=eval_res.analytical_status,
                regulatory_tier=eval_res.regulatory_tier,
                is_safe_to_drink=eval_res.is_safe_to_drink,
                uncertainty_ppb=eval_res.uncertainty_ppb,
                confidence=0.90,
                source_type=payload.source_type or "manual_import",
                is_simulated=payload.source_type != "hardware",
                method_version=METHOD_NAME,
                model_version="AquaNet-V1" if os.getenv("AQUANET_MODEL", "v3").lower() == "v1" else "AquaNet-V3",
                idempotency_key=idemp,
                ph=ph,
                temperature_c=temp,
                conductivity_us_cm=cond,
                turbidity_ntu=turb,
                latitude=float(r.get("latitude", 18.5204)) if r.get("latitude") is not None else None,
                longitude=float(r.get("longitude", 73.8567)) if r.get("longitude") is not None else None,
                source_label=r.get("source_label", "Imported Dataset"),
                recorded_at=now_utc(),
                received_at=now_utc(),
            )
            db.add(rec)
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
    db: Session = Depends(get_db),
):
    """Export water quality readings with complete scientific schema versioning and lineage."""
    q = db.query(models.Reading).order_by(models.Reading.recorded_at.desc())
    if source_type:
        q = q.filter(models.Reading.source_type == source_type)
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

@app.post("/api/demo/load", tags=["Demo Management"])
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
            model_version="AquaNet-V1" if os.getenv("AQUANET_MODEL", "v3").lower() == "v1" else "AquaNet-V3",
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
    as_mg = payload.arsenic_mg_l or payload.arsenic_concentration_mg_l
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
  * India BIS 10500 Acceptable: 10.0 µg/L; Permissible: 50.0 µg/L.
- CRITICAL SCIENTIFIC FACT: Because the sensor's LOD (20 µg/L) is higher than the WHO guideline (10 µg/L), readings below 20 µg/L CANNOT confirm compliance with the 10 µg/L WHO guideline. Always explain this transparently.

Multi-Contaminant Sensing Policy:
- The current AquaSentry physical robot ONLY has an ASV sensor for Arsenic (As).
- Lead, Cadmium, Mercury, Chromium, Fluoride, and Nitrate are cataloged capabilities but require dedicated sensor modules or external laboratory testing. Never claim the single arsenic strip detects all metals simultaneously.

Neural Network (AquaNet-V1):
- Architecture: 5-8-6-4 Dense Multi-Layer Perceptron (MLP).
- Exact Topology: 23 Nodes, 112 Synapses (5*8 + 8*6 + 6*4 = 40 + 48 + 24 = 112 connections).
- Inputs: Dissolved Arsenic (mg/L), pH, Electrical Conductivity (µS/cm), Turbidity (NTU), Temperature (°C).
- Outputs: Safe, Caution, Unsafe, Hazardous.
- How it was made: V1's weights were set by hand from the WHO/BIS arsenic thresholds (they were not learned from data). Only the arsenic input affects V1's vote; pH, turbidity and conductivity are checked by fixed safety rules after the network. A trained version, AquaNet-V2, learns all five inputs from 300,000 synthetic samples (99.6% correct on synthetic test data). Neither has been validated on real field samples.
- Precedence Rule: The model can never downgrade a measured reading > 50 µg/L to Safe.

Robot Hardware Specs:
- Twin-hull catamaran (1.05m x 0.62m, 11.4kg displacement).
- Solar 6V/5W + 18650 Li-ion 3000mAh buffer; 6-hour duty cycle consuming 0.6-1.0 Wh/day.
- Non-immersion microfluidic sampling: 15 mL peristaltic pump chamber protects sensors from open-water biofilm fouling.
- Communications: LoRa (2 km+) + HC-05 Bluetooth + GPS geotagging.
"""


@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["AI Chat"])
async def chat(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """
    Intelligent chatbot endpoint with server-side intent classification,
    grounded database context, and public health guardrails.
    """
    # 1. Server-side Intent Gate & Prompt Injection Filter
    intent, preformatted = classify_user_prompt(request.message)
    if preformatted:
        return schemas.ChatResponse(reply=preformatted, intent=intent.value, grounded=False)

    if not client:
        return schemas.ChatResponse(
            reply=(
                "⚠️ **AquaSentry AI Assistant (Offline Mode):**\n\n"
                "The live Gemini AI model is currently not configured. To activate the AI Assistant, "
                "please obtain a free API key from Google AI Studio and configure `GEMINI_API_KEY` "
                "in your `.env` file.\n\n"
                "*All dashboard sensors, the AquaNet-V1 neural network visualizer, and ASV simulations "
                "continue to operate completely offline in your browser!*"
            ),
            intent="in_scope",
            grounded=False,
        )

    # 2. Retrieve Latest Reading from Database for Grounding
    latest_rec = db.query(models.Reading).order_by(models.Reading.recorded_at.desc()).first()
    latest_dict = None
    if latest_rec:
        latest_dict = {
            "arsenic_ppb": latest_rec.arsenic_ppb,
            "arsenic_mg_l": round(latest_rec.arsenic_ppb / 1000.0, 4),
            "analytical_status": latest_rec.analytical_status,
            "regulatory_tier": latest_rec.regulatory_tier,
            "source_type": latest_rec.source_type,
            "recorded_at": latest_rec.recorded_at.isoformat() if latest_rec.recorded_at else "Just now",
            "is_safe_to_drink": latest_rec.is_safe_to_drink,
        }

    grounded_context = format_grounded_context(latest_dict)
    dynamic_prompt = BASE_SYSTEM_PROMPT + "\n" + grounded_context

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=request.message,
            config=types.GenerateContentConfig(
                system_instruction=dynamic_prompt,
                temperature=0.2,
            ),
        )
        return schemas.ChatResponse(reply=response.text, intent="in_scope", grounded=True)
    except Exception as e:
        error_str = str(e)
        if "503" in error_str or "high demand" in error_str:
            return schemas.ChatResponse(
                reply="⚠️ *Notice:* Google AI servers are temporarily experiencing high global demand. Please try your question again in a minute.",
                intent="in_scope",
                grounded=False,
            )
        return schemas.ChatResponse(
            reply=f"⚠️ *AI Notice:* Could not complete request: {error_str}",
            intent="in_scope",
            grounded=False,
        )


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
            cmd = data.get("command", "start_sweep")
            as_conc = float(data.get("arsenic_mg_l", 0.035))

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
    if reading_id:
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
    }
    # Model confidence is recomputed from the stored values (defaults only where a sensor was not fitted).
    try:
        nn = forward_pass(
            arsenic_mg_l=data["arsenic_mg_l"],
            ph=rec.ph if rec.ph is not None else 7.2,
            conductivity_us_cm=rec.conductivity_us_cm if rec.conductivity_us_cm is not None else 400.0,
            turbidity_ntu=rec.turbidity_ntu if rec.turbidity_ntu is not None else 2.0,
            temperature_c=rec.temperature_c if rec.temperature_c is not None else 24.0,
        )
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
def get_recent_alerts():
    """Retrieve recent emergency water quality exceedance alerts."""
    return {
        "count": len(RECENT_EMERGENCY_ALERTS),
        "alerts": list(reversed(RECENT_EMERGENCY_ALERTS[-20:])),
    }


# ===========================================================================
# Imp 22: SQLite WAL Compaction Endpoint
# ===========================================================================

@app.post("/api/admin/db/compact", tags=["Admin"])
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
