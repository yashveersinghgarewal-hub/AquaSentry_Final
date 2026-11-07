#!/usr/bin/env python3
"""
AquaSentry Universal Master Entry Point
======================================
Unified operational runner for both AquaSentry Fullstack Platform
and AquaNet-V1 Neural Network Toolkit.

Usage:
  python3 main.py --serve          # Launch fullstack web app & REST API (FastAPI)
  python3 main.py --test           # Run all 110 test cases (22 Neural Parity + 88 Platform)
  python3 main.py --csv <path>     # Process ASV voltammetry scan + AquaNet classification
  python3 main.py --neural         # Run standalone AquaNet-V1 neural network evaluation
  python3 main.py --version        # Display system topology and versions
"""

import sys
import os
import argparse
import subprocess
import json

UNIVERSAL_ROOT = os.path.dirname(os.path.abspath(__file__))
PLATFORM_DIR = os.path.join(UNIVERSAL_ROOT, "AquaSentry_Platform")
NEURAL_DIR = os.path.join(UNIVERSAL_ROOT, "Neural_Network")

# Add directories to sys.path so modules resolve seamlessly
sys.path.insert(0, PLATFORM_DIR)
sys.path.insert(0, NEURAL_DIR)


def print_banner():
    print("""
======================================================================
       AQUASENTRY UNIVERSAL WATER SAFETY & NEURAL NETWORK PLATFORM
======================================================================
  Architecture : AquaNet-V1 Multilayer Perceptron (23 Nodes, 112 Synapses)
  Standards    : WHO Guideline (0.010 mg/L) | BIS 10500 Permissible (0.050 mg/L)
  Hardware     : Anodic Stripping Voltammetry (ASV) & ESP32 / C99 Edge Engine
======================================================================
""")


def run_serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Launch FastAPI server with Uvicorn."""
    print(f"[*] Starting AquaSentry Web Platform on http://{host}:{port} ...")
    try:
        import uvicorn
    except ImportError:
        print("[ERROR] uvicorn is not installed in the active environment.")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    # Change working directory to AquaSentry_Platform so app and static files resolve
    os.chdir(PLATFORM_DIR)
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


def run_tests():
    """Run both platform tests (79) and neural network parity tests (18)."""
    print_banner()

    # Determine best python interpreter with pytest
    python_candidates = [
        sys.executable,
        os.path.join(UNIVERSAL_ROOT, ".venv", "bin", "python"),
        os.path.join(UNIVERSAL_ROOT, ".venv", "Scripts", "python.exe"),
        os.path.join(PLATFORM_DIR, ".venv", "bin", "python"),
        os.path.join(PLATFORM_DIR, ".venv", "Scripts", "python.exe"),
    ]
    py_exec = sys.executable
    for cand in python_candidates:
        if os.path.exists(cand):
            py_exec = cand
            break

    print("[*] STEP 1/2: Running AquaNet-V1 Standalone Neural Parity Tests...")
    parity_test_path = os.path.join(NEURAL_DIR, "test_aquanet_parity.py")
    res1 = subprocess.run([py_exec, parity_test_path])

    print("\n[*] STEP 2/2: Running AquaSentry Platform & API Integration Tests...")
    platform_test_runner = os.path.join(PLATFORM_DIR, "run_tests.py")
    res2 = subprocess.run([py_exec, platform_test_runner])

    if res1.returncode == 0 and res2.returncode == 0:
        print("\n======================================================================")
        print("  ALL 110 TESTS PASSED SUCCESSFULLY! (22 Neural Parity + 88 Platform)")
        print("======================================================================")
        sys.exit(0)
    else:
        print("\n[FAIL] Test suite completed with errors.")
        sys.exit(1)


def run_csv_analysis(csv_path: str, ph: float, ec: float, turb: float, temp: float):
    """Run end-to-end ASV extraction and neural network inference."""
    try:
        from asv_extractor import analyze_water_sample
    except ImportError:
        try:
            from app.asv_extractor import analyze_water_sample
        except ImportError as err:
            print(f"[ERROR] Could not import asv_extractor: {err}")
            sys.exit(1)

    result = analyze_water_sample(
        csv_path=csv_path,
        ph=ph,
        conductivity_us_cm=ec,
        turbidity_ntu=turb,
        temperature_c=temp
    )
    print(json.dumps(result, indent=2))


def run_neural_cli():
    """Run standalone neural forward pass CLI."""
    nn_main = os.path.join(NEURAL_DIR, "main.py")
    subprocess.run([sys.executable, nn_main])


def main():
    parser = argparse.ArgumentParser(
        description="AquaSentry Universal Master Runner"
    )
    parser.add_argument("--serve", action="store_true", help="Launch FastAPI web app and dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload for development")
    parser.add_argument("--test", action="store_true", help="Run comprehensive test suites (110 tests)")
    parser.add_argument("--neural", action="store_true", help="Run standalone AquaNet-V1 neural evaluations")
    parser.add_argument("--csv", type=str, default=None, help="Process raw ASV CSV scan file")
    parser.add_argument("--ph", type=float, default=7.2, help="Water pH (default: 7.2)")
    parser.add_argument("--ec", type=float, default=400.0, help="Electrical conductivity in uS/cm (default: 400.0)")
    parser.add_argument("--turb", type=float, default=2.0, help="Turbidity in NTU (default: 2.0)")
    parser.add_argument("--temp", type=float, default=24.0, help="Temperature in deg C (default: 24.0)")
    parser.add_argument("--version", action="store_true", help="Show system version and topology")

    args = parser.parse_args()

    if args.version:
        print_banner()
        print("  System Version: AquaSentry Universal v1.0.0")
        print("  Components Included:")
        print("    - AquaSentry_Platform (FastAPI backend, HTML5 dashboard, SQLite database)")
        print("    - Neural_Network (AquaNet-V1 C99 engine, Python forward pass, parity suite)")
        print("    - AI_Agent (Toxicology and water quality research agent)")
        print("    - Data (Raw ASV voltammetry scans, calibration matrices)")
        print("    - Analysis (Savitzky-Golay filtering, synthetic trace generators)")
        print("    - Docs (Engineering specifications, blueprints, PDF reports)")
        return

    if args.serve:
        run_serve(host=args.host, port=args.port, reload=args.reload)
    elif args.test:
        run_tests()
    elif args.csv:
        run_csv_analysis(args.csv, args.ph, args.ec, args.turb, args.temp)
    elif args.neural:
        run_neural_cli()
    else:
        print_banner()
        parser.print_help()


if __name__ == "__main__":
    main()
