"""
AquaNet-V1: Multimodal Deep Neural Network for Autonomous Water Surveillance.
Standalone Training, ASV Signal Processing & Edge Inference Execution Suite.

Topology: 5 Input Features -> 8 Hidden (ReLU) -> 6 Hidden (ReLU) -> 4 Output Classes (Softmax)
Total Nodes: 23 | Total Synapses: 112 | Weights hand-constructed from the arsenic limits
"""

import sys
import json
import argparse
from aquanet_classifier import forward_pass, AquaNetV1, NODES_COUNT, SYNAPSES_COUNT, CLASSES
from asv_extractor import analyze_water_sample

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
    print("[*] For custom physical inputs: python3 main.py --as 0.045 --ph 7.4 --ec 450 --turb 3.0 --temp 25")
    print("[*] For raw ASV voltammogram trace: python3 main.py --csv example_data.csv --cal calibration.json")
    print("[*] To verify parity tests: python3 test_aquanet_parity.py")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AquaNet-V1 Neural Network Inference")
    parser.add_argument("--as_conc", "--as", type=float, default=None, help="Arsenic in mg/L (e.g. 0.045)")
    parser.add_argument("--ph", type=float, default=7.2, help="Water pH (e.g. 7.2)")
    parser.add_argument("--ec", type=float, default=400.0, help="Electrical conductivity in uS/cm (e.g. 400.0)")
    parser.add_argument("--turb", type=float, default=2.0, help="Turbidity in NTU (e.g. 2.0)")
    parser.add_argument("--temp", type=float, default=24.0, help="Water temperature in C (e.g. 24.0)")
    parser.add_argument("--csv", type=str, default=None, help="Path to raw voltammetry CSV sweep")
    parser.add_argument("--cal", type=str, default="calibration.json", help="Path to calibration JSON")

    args = parser.parse_args()

    if args.csv is not None:
        result = analyze_water_sample(
            csv_path=args.csv,
            calibration_path=args.cal,
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
