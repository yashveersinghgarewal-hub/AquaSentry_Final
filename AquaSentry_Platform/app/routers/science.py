"""Contaminant catalogue, voltammetry signal processing (HTTP + WebSocket stream) and neural-network demos."""
import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from .. import schemas
from ..analytes import get_analyte_profile, list_supported_analytes
from ..neural_classifier import forward_pass
from ..signal_processing import generate_synthetic_asv_trace, process_voltammetry_trace

router = APIRouter()

# ---------------------------------------------------------------------------
# Multi-Contaminant & Analyte Registry Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/analytes", response_model=List[schemas.AnalyteCapabilityOut], tags=["Contaminants"])
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


@router.get("/api/analytes/{analyte_id}", response_model=schemas.AnalyteCapabilityOut, tags=["Contaminants"])
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

@router.post("/api/voltammetry/process", response_model=schemas.VoltammetryProcessResponse, tags=["Electrochemistry"])
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
            baseline_slope_ua_per_mv=res.peak.baseline_slope_ua_per_mv,
            noise_sigma_ua=res.peak.noise_sigma_ua,
            secondary_peaks=res.peak.secondary_peaks,
            uncertainty_ug_l=res.peak.uncertainty_ug_l,
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
        analysis_version=res.analysis_version,
        sweep_reversed=res.sweep_reversed,
    )


@router.get("/api/voltammetry/sample-trace", response_model=schemas.SyntheticTraceResponse, tags=["Electrochemistry"])
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
# AquaNet-V1 Neural Network Inference Endpoints (GET & POST)
# ---------------------------------------------------------------------------

class NeuralInferencePayload(schemas.BaseModel):
    """v5.8 (review item 43): bounded, finite inputs only; a negative or infinite concentration is rejected."""
    arsenic_concentration_mg_l: Optional[float] = schemas.Field(None, ge=0, le=50, allow_inf_nan=False)
    arsenic_mg_l: Optional[float] = schemas.Field(None, ge=0, le=50, allow_inf_nan=False)
    arsenic_ppb: Optional[float] = schemas.Field(None, ge=0, le=50000, allow_inf_nan=False)
    ph: Optional[float] = schemas.Field(7.35, ge=0, le=14, allow_inf_nan=False)
    conductivity_us_cm: Optional[float] = schemas.Field(412.0, ge=0, le=50000, allow_inf_nan=False)
    turbidity_ntu: Optional[float] = schemas.Field(2.1, ge=0, le=1000, allow_inf_nan=False)
    temperature_c: Optional[float] = schemas.Field(24.2, ge=-10, le=60, allow_inf_nan=False)


@router.post("/api/neural/inference", response_model=schemas.NeuralInferenceResponse, tags=["Neural Network"])
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


@router.get("/api/neural/v3", tags=["Neural Network"])
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


@router.get("/api/neural/inference", response_model=schemas.NeuralInferenceResponse, tags=["Neural Network"])
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


# ===========================================================================
# Imp 19: WebSocket Real-Time Voltammetry Streaming Endpoint
# ===========================================================================

@router.websocket("/ws/voltammetry")
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

