"""Screening-report PDF ("potability certificate") generation and download."""
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import _val, active_model_name
from ..neural_classifier import forward_pass
from ..standards import CALIBRATION_INTERCEPT, CALIBRATION_SLOPE, HAZARD_THRESHOLD_UG_L, LOD_UG_L

router = APIRouter()

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


# ===========================================================================
# Imp 20: Screening Report PDF Endpoint
# ===========================================================================

@router.get("/api/reports/certificate/pdf", tags=["Reports"])
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

