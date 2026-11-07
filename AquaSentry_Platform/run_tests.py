"""AquaSentry Automated Test Suite Runner.
Executes all scientific standards, neural parity, and API contract tests.
Exits with code 0 on success, non-zero on failure.
"""

import os
import sys

try:
    import pytest
except ImportError:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    python_candidates = [
        os.path.join(script_dir, ".venv", "bin", "python"),
        os.path.join(script_dir, ".venv", "Scripts", "python.exe"),
        os.path.join(parent_dir, ".venv", "bin", "python"),
        os.path.join(parent_dir, ".venv", "Scripts", "python.exe"),
    ]
    venv_python = None
    for cand in python_candidates:
        if os.path.exists(cand):
            venv_python = cand
            break

    if venv_python and sys.executable != venv_python:
        import subprocess
        result = subprocess.run([venv_python, __file__] + sys.argv[1:])
        sys.exit(result.returncode)
    else:
        print("Error: pytest is not installed. Run with .venv/bin/python or install pytest.")
        sys.exit(1)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print("=" * 70)
    print("AquaSentry Comprehensive Test Suite Execution")
    print("Testing Scientific Standards, Neural Parity (112 Synapses), and API Contracts")
    print("=" * 70)
    
    args = ["-v", "tests"]
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
        
    exit_code = pytest.main(args)
    sys.exit(exit_code)
