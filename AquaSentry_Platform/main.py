"""
AquaSentry Universal Command Center & Neural Inference Engine.

Unified entry point:
1. Scenario Benchmarks:     python main.py
2. Single Water Prediction: python main.py --as 0.042 --ph 7.4 --ec 450 --turb 2.5 --temp 24
3. ASV Voltammogram Trace:  python main.py --csv data/example_data.csv --cal data/calibration.json
4. Launch Web API Server:   python main.py --serve [--port 8000]
5. Run Parity & Unit Tests: python main.py --test
"""

import os
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from app.neural_classifier import forward_pass, AquaNetV1, NODES_COUNT, SYNAPSES_COUNT, CLASSES
from app.asv_extractor import analyze_water_sample


def run_sample_inferences():
    print("=" * 75)
    print(f"AquaNet-V1 Neural Network Inference Engine ({NODES_COUNT} Nodes, {SYNAPSES_COUNT} Synapses)")
    print("Hand-constructed threshold weights (arsenic only); safety rules handle pH, turbidity, conductivity")
    print("=" * 75)

    scenarios = [
        {"name": "Clean Groundwater Spring", "as": 0.005, "ph": 7.20, "ec": 280.0, "turb": 1.2, "temp": 21.0},
        {"name": "Mild Arsenic Exceedance (BIS Permissible)", "as": 0.035, "ph": 7.60, "ec": 520.0, "turb": 3.8, "temp": 24.5},
        {"name": "Severe Agricultural Contamination", "as": 0.085, "ph": 8.10, "ec": 840.0, "turb": 14.5, "temp": 28.0},
        {"name": "Acute Toxic Industrial Runoff", "as": 0.350, "ph": 8.90, "ec": 1850.0, "turb": 42.0, "temp": 31.0},
        {"name": "Geochemical Multi-Hazard (Acidic Runoff with Low Arsenic)", "as": 0.005, "ph": 4.80, "ec": 650.0, "turb": 2.5, "temp": 22.0},
        {"name": "High Turbidity Silt Infiltration", "as": 0.008, "ph": 7.40, "ec": 410.0, "turb": 25.0, "temp": 23.5},
    ]

    for sc in scenarios:
        res = forward_pass(
            arsenic_mg_l=sc["as"],
            ph=sc["ph"],
            conductivity_us_cm=sc["ec"],
            turbidity_ntu=sc["turb"],
            temperature_c=sc["temp"],
        )
        print(f"\nScenario: {sc['name']}")
        print(f"  Inputs: Arsenic={sc['as']} mg/L, pH={sc['ph']}, EC={sc['ec']} uS/cm, Turb={sc['turb']} NTU, Temp={sc['temp']} C")
        print(f"  Result: [{res['predicted_class'].upper()}] (Raw Model: {res['raw_model_class']}, Confidence: {res['confidence_pct']}%, Latency: {res['latency_ms']} ms)")
        print(f"  Class Probabilities: {res['probabilities']}")
        if res["reason_codes"]:
            print(f"  Active Policy & Guardrail Advisories:")
            for r in res["reason_codes"]:
                print(f"    - {r}")

    print("\n" + "=" * 75)
    print("[*] Interactive single prediction: python main.py --as 0.045 --ph 7.4 --ec 450 --turb 3.0 --temp 25")
    print("[*] Raw ASV trace extraction:      python main.py --csv data/example_data.csv --cal data/calibration.json")
    print("[*] Launch full web platform:      python main.py --serve --port 8000")
    print("[*] Run comprehensive tests:       python main.py --test")
    print("=" * 75)


def run_tests_suite():
    venv_python = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")
    py_exec = venv_python if os.path.exists(venv_python) else sys.executable
    import subprocess
    cmd = [py_exec, os.path.join(SCRIPT_DIR, "run_tests.py")]
    sys.exit(subprocess.run(cmd).returncode)


def run_server(port=8000, host="0.0.0.0"):
    venv_python = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")
    py_exec = venv_python if os.path.exists(venv_python) else sys.executable
    import subprocess
    cmd = [py_exec, "-m", "uvicorn", "app.main:app", f"--host={host}", f"--port={port}", "--reload"]
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AquaSentry Universal Surveillance Platform & Neural Classifier")
    parser.add_argument("--as_conc", "--as", type=float, default=None, help="Arsenic in mg/L (e.g. 0.045)")
    parser.add_argument("--ph", type=float, default=7.2, help="Water pH (e.g. 7.2)")
    parser.add_argument("--ec", type=float, default=400.0, help="Electrical conductivity in uS/cm (e.g. 400.0)")
    parser.add_argument("--turb", type=float, default=2.0, help="Turbidity in NTU (e.g. 2.0)")
    parser.add_argument("--temp", type=float, default=24.0, help="Water temperature in C (e.g. 24.0)")
    parser.add_argument("--csv", type=str, default=None, help="Path to raw voltammetry CSV sweep")
    parser.add_argument("--cal", type=str, default="data/calibration.json", help="Path to calibration JSON")
    parser.add_argument("--serve", action="store_true", help="Launch the AquaSentry FastAPI server & web UI")
    parser.add_argument("--port", type=int, default=8000, help="Port to run web server on (default 8000)")
    parser.add_argument("--test", action="store_true", help="Execute comprehensive automated test suite")

    args = parser.parse_args()

    if args.serve:
        run_server(port=args.port)
    elif args.test:
        run_tests_suite()
    elif args.csv is not None:
        csv_path = args.csv
        if not os.path.exists(csv_path) and os.path.exists(os.path.join(SCRIPT_DIR, "data", csv_path)):
            csv_path = os.path.join(SCRIPT_DIR, "data", csv_path)
        cal_path = args.cal
        if not os.path.exists(cal_path) and os.path.exists(os.path.join(SCRIPT_DIR, "data", cal_path)):
            cal_path = os.path.join(SCRIPT_DIR, "data", cal_path)
            
        result = analyze_water_sample(
            csv_path=csv_path,
            calibration_path=cal_path if os.path.exists(cal_path) else None,
            ph=args.ph,
            conductivity_us_cm=args.ec,
            turbidity_ntu=args.turb,
            temperature_c=args.temp,
        )
        print(json.dumps(result, indent=2))
    elif args.as_conc is not None:
        result = forward_pass(args.as_conc, args.ph, args.ec, args.turb, args.temp)
        print(json.dumps(result, indent=2))
    else:
        run_sample_inferences()
