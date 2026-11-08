# AquaNet-V3 training code

Everything needed to retrain, test and install the V3 network. Needs only Python 3 and NumPy (plus `gcc` for the C check).
Results and explanation: `Docs/neural/AQUANET_V3_REPORT.md`.

| File | What it does |
| --- | --- |
| `train_v3.py` | Trains V3. `clean` mode = exact readings, `noisy` mode = readings with sensor noise (graded on the true water). |
| `eval_v3.py` | Compares models: network alone on exact readings, and the whole system (network + safety rules) with a noisy sensor. |
| `eval_adaptive.py` | Tests the ESP32's adaptive re-scan rule (3 scans, more only near a limit) against fixed 3 / 6 / 9 scans. |
| `add_test_metrics.py` | Copies a model and attaches its test results (the dashboard shows these). |
| `parity_v3.py` | Compiles the generated C engine and checks it gives the same answers as Python on 100,000 inputs. |
| `make_v3_report.py` | Writes `Docs/neural/AQUANET_V3_REPORT.md` from the evaluation results. |
| `models/` | The installed model and the alternatives, ready to install. |
| `results/` | Evaluation output and training logs from this round. |

## Retrain (from the `Neural_Network/v3_training` folder)

```bash
# 3-scan noise (matches the firmware), balanced weighting, two sizes, several random starts
SCANS=3 W_DANGER=2 W_CAUTION=1.5 TAG=_bal_s3 python train_v3.py noisy out "5x8x6x4:0,1,2;5x16x12x4:0,1"

# evaluate against V1, V2 and anything else (SCANS sets the noise used in the test)
SCANS=3 python eval_v3.py ../aquanet_v1_weights.json ../aquanet_v2_weights.json out/noisy_bal_s3_5x16x12x4_best.json > eval_s3.json
SCANS=1 python eval_v3.py ../aquanet_v1_weights.json ../aquanet_v2_weights.json out/noisy_bal_s3_5x16x12x4_best.json > eval_s1.json

# attach results and install into server + dashboard + ESP32 code
python add_test_metrics.py out/noisy_bal_s3_5x16x12x4_best.json eval_s1.json eval_s3.json my_model.json
cd ../../AquaSentry_Platform && python scripts/install_aquanet_v3.py ../Neural_Network/v3_training/my_model.json
python ../main.py --test
```
On Windows PowerShell set the variables first, e.g. `$env:SCANS=3; $env:W_DANGER=2; ...`.

Settings (environment variables): `AS_EDGES` arsenic class edges in µg/L (default `10,20,150` = the IS 10500 / WHO 10 µg/L limit, the 20 µg/L detection limit and the hazard level; `10,50,150` reproduces models from before v5.2), `SCANS` scans averaged per reading, `ADAPTIVE=1` use the firmware's adaptive re-scan rule instead (3 → 6 → 9 scans while within `ADAPT_Z` standard errors of a limit; must match `RESCAN_Z` in the firmware), `W_DANGER` / `W_CAUTION` extra training weight for Unsafe-Hazardous / Caution samples, `EPOCHS`, `NTRAIN` training samples, `TAG` added to the output file name.

**Keep the network ESP32-sized:** the tests allow up to 600 weights. 5-8-6-4 = 130, 5-16-12-4 = 352.

**When you have real lab data:** replace the synthetic `sample()` / `measure()` in `train_v3.py` with your measured readings and lab results, and set the noise figures to what your electrode actually shows.
