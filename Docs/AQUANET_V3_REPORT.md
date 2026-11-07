# AquaNet-V3 — training report

**Installed model:** `noisy_mid_s3_5x16x12x4` (file `Neural_Network/aquanet_v3_weights.json`, same weights in `AquaSentry_Platform/app/`, the dashboard and `Firmware/esp32_firmware/aquanet_v3.c`).

## What V3 changes

1. **Arsenic goes in on a log scale.** The network sees log10(arsenic + 0.001) instead of raw mg/L. The 10, 50 and 150 µg/L limits are then evenly spaced instead of crushed together near zero, which makes them much easier to learn.
2. **Trained on noisy readings.** A real sensor never reads the exact value. During training each sample is "measured" with the sensor errors stated in `app/standards.py` (arsenic ±5 µg/L below 50 µg/L, ±7.5 up to 150, ±15 above; pH ±0.1; conductivity ±3%; turbidity ±0.3 NTU + 5%; temperature ±0.5 °C). The network sees the measured value but is graded on the class of the *true* water, so it learns how likely a reading close to a limit is to really be over it.
3. **Matched to the ESP32.** The firmware averages at least 3 scans per reading, which shrinks the arsenic error by √3 or more. The installed model was trained with 3-scan noise.
4. **Weighted for safety.** Missing Unsafe/Hazardous water costs more in training than a false alarm (installed model: class weights Caution ×1.75, Unsafe/Hazardous ×3), and the training picks the model that never calls dangerous water Safe.
5. **Safety rules still run after the network** on the server, the dashboard and the ESP32. They can only make the answer stricter.
6. **Adaptive re-scanning (v4.1).** The ESP32 takes 3 scans; if the arsenic reading is within 2 standard errors of 10, 50 or 150 µg/L it takes 3 more, and again up to 9. See *Result 3*.

Training: Adam optimiser, cosine learning-rate schedule, 260,000–500,000 fresh synthetic samples per run (half of them deliberately close to a limit), several random starts per size, best kept by validation. Sizes tried: 5-8-6-4 (130 weights) and 5-16-12-4 (352 weights). Both fit easily on an ESP32; 5-16-12-4 is 1.4 KB of flash.

## Result 1 — the network alone, on exact readings

100,000 test samples it never saw. "Near the limits" = every sample is placed close to one of the limits (the hardest case).

| Model | Correct | Correct near the limits | Dangerous water called Safe |
| --- | --- | --- | --- |
| V1 (hand-built, arsenic only) | 73.4% | 62.6% | 8,410 |
| V2 (trained on exact readings) | 99.6% | 99.1% | 0 |
| **V3 5-16-12-4 — installed** | 98.6% | 97.0% | 0 |
| V3 5-16-12-4 safety-first (included as an option) | 97.1% | 94.4% | 0 |

V2 scores a little higher here because it was trained on exact values. V3 is deliberately cautious next to a limit, because in real use a reading there could be on either side.

## Result 2 — the whole system with a noisy sensor (what matters in the field)

200,000 simulated water samples. Each one is measured with sensor noise, then the network **and** the safety rules give the final verdict, which is compared with the class of the real water.

**Realistic water, 3 scans averaged (what the ESP32 firmware does):**

| Model | Final verdict correct | Unsafe/Hazardous water missed (called Safe or Caution) | Change in misses vs rules alone | False alarms | Dangerous water called Safe |
| --- | --- | --- | --- | --- | --- |
| Safety rules alone (no network) | 93.6% | 2,283 | — | 6,742 | 0 |
| V2 (trained on exact readings) | 93.6% | 2,152 | −6% | 7,103 | 0 |
| **V3 5-16-12-4 — installed** | 93.5% | 1,755 | −23% | 8,180 | 0 |
| V3 5-16-12-4 safety-first (included as an option) | 93.0% | 1,384 | −39% | 9,920 | 0 |

**Realistic water, 1 scan:**

| Model | Final verdict correct | Unsafe/Hazardous water missed (called Safe or Caution) | Change in misses vs rules alone | False alarms | Dangerous water called Safe |
| --- | --- | --- | --- | --- | --- |
| Safety rules alone (no network) | 91.1% | 2,783 | — | 10,041 | 0 |
| V2 (trained on exact readings) | 91.1% | 2,656 | −5% | 10,419 | 0 |
| **V3 5-16-12-4 — installed** | 91.0% | 2,260 | −19% | 11,513 | 0 |
| V3 5-16-12-4 safety-first (included as an option) | 90.6% | 1,874 | −33% | 13,158 | 0 |

**Samples close to the limits, 3 scans:**

| Model | Final verdict correct | Unsafe/Hazardous water missed (called Safe or Caution) | Change in misses vs rules alone | False alarms | Dangerous water called Safe |
| --- | --- | --- | --- | --- | --- |
| Safety rules alone (no network) | 88.6% | 6,746 | — | 11,001 | 0 |
| V2 (trained on exact readings) | 88.6% | 6,285 | −7% | 11,700 | 0 |
| **V3 5-16-12-4 — installed** | 88.4% | 5,196 | −23% | 13,942 | 0 |
| V3 5-16-12-4 safety-first (included as an option) | 87.9% | 4,086 | −39% | 16,559 | 0 |

## Result 3 — adaptive re-scanning on the ESP32 (v4.1)

Same 200,000 simulated samples; each one is scanned 9 times in the simulation and the firmware's rule decides how many of those scans it would actually use. A scan takes about 70 seconds (2 s clean + 60 s deposit + sweep).

**Realistic water:**

| Model | Scanning | Average scans per test | Tests re-scanned | Final verdict correct | Dangerous missed | False alarms | Dangerous called Safe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| installed model | Fixed 3 scans (v4) | 3.0 | 0% | 93.4% | 1,759 | 8,183 | 0 |
| installed model | **Adaptive 3 → 9 (v4.1)** | 4.4 | 29% | 94.6% | 1,508 | 6,836 | 0 |
| installed model | Fixed 6 scans | 6.0 | 100% | 94.3% | 1,542 | 7,234 | 0 |
| installed model | Fixed 9 scans | 9.0 | 100% | 94.6% | 1,467 | 6,856 | 0 |
| safety-first model | Fixed 3 scans (v4) | 3.0 | 0% | 93.0% | 1,394 | 9,913 | 0 |
| safety-first model | **Adaptive 3 → 9 (v4.1)** | 4.4 | 29% | 94.1% | 1,206 | 8,518 | 0 |
| safety-first model | Fixed 6 scans | 6.0 | 100% | 93.8% | 1,211 | 8,955 | 0 |
| safety-first model | Fixed 9 scans | 9.0 | 100% | 94.1% | 1,143 | 8,604 | 0 |

**Samples close to the limits:**

| Model | Scanning | Average scans per test | Tests re-scanned | Final verdict correct | Dangerous missed | False alarms | Dangerous called Safe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| installed model | Fixed 3 scans (v4) | 3.0 | 0% | 88.4% | 5,150 | 13,917 | 0 |
| installed model | **Adaptive 3 → 9 (v4.1)** | 4.8 | 36% | 89.5% | 4,752 | 12,841 | 0 |
| installed model | Fixed 6 scans | 6.0 | 100% | 89.2% | 4,844 | 13,236 | 0 |
| installed model | Fixed 9 scans | 9.0 | 100% | 89.7% | 4,688 | 12,864 | 0 |
| safety-first model | Fixed 3 scans (v4) | 3.0 | 0% | 87.9% | 4,065 | 16,569 | 0 |
| safety-first model | **Adaptive 3 → 9 (v4.1)** | 4.8 | 36% | 89.1% | 3,739 | 15,502 | 0 |
| safety-first model | Fixed 6 scans | 6.0 | 100% | 88.7% | 3,784 | 15,904 | 0 |
| safety-first model | Fixed 9 scans | 9.0 | 100% | 89.1% | 3,656 | 15,591 | 0 |

Adaptive scanning gets almost all the benefit of always doing 9 scans for about half the time: most water is clearly on one side of every limit and finishes after 3 scans; only borderline readings get the extra scans. A borderline test takes up to about 10½ minutes, well inside the 1-hour testing interval. Settings: `SCANS_PER_READING`, `MAX_SCANS_PER_READING` and `RESCAN_Z` at the top of `esp32_firmware.ino` (the tests check they match the training code).

## How to read this

- **In the whole-system tests no model ever called dangerous water "Safe"**, because the safety rules always run last. (The V1 network on its own did, 8,410 times — that is why the rules exist.)
- **Why overall accuracy can't go much above the rules alone:** the network is only allowed to make a verdict stricter, never softer. So it can't fix the cases where the sensor reads just over a limit but the water is really just under it. Allowing that would mean sometimes calling a reading of 52 µg/L something milder than "Unsafe", which we won't do for drinking water.
- With a fixed number of scans, end-to-end accuracy is capped by the **measurement noise**, not by the network: if the sensor reads 48 µg/L the water might really be 52. No network can know which. That is why v4.1 attacks the noise itself: adaptive re-scanning (Result 3) lifts accuracy by more than a point. Further gains need a better-calibrated electrode, real lab-tested training data, or a lab check for borderline readings.
- What the network *can* do is choose which way to lean near a limit. The installed model stays within 0.2 points of the rules' overall accuracy while missing about a quarter fewer Unsafe/Hazardous samples. The safety-first option misses far fewer dangerous samples (about 40% fewer) at the cost of more false alarms (water flagged as worse than it is). For a drinking-water screening tool, false alarms are the cheaper mistake — switch to it if your team prefers that trade:

```
cd AquaSentry_Platform
python scripts/install_aquanet_v3.py ../Neural_Network/v3_training/models/aquanet_v3_safety_first.json
```

A third option, `aquanet_v3_fewest_false_alarms.json` (trained without extra danger weighting), has the highest exact-reading accuracy of all V3 models and almost exactly the same field behaviour as the rules alone. To go back to the installed model, install `aquanet_v3_installed_balanced.json` the same way.

## All candidates trained in this round (realistic water, 3 scans)

| Candidate | Exact-reading accuracy | End-to-end accuracy | Dangerous missed | False alarms |
| --- | --- | --- | --- | --- |
| `rules only` | — | 93.6% | 2,283 | 6,742 |
| `v2` | 99.6% | 93.6% | 2,152 | 7,103 |
| `noisy_5x16x12x4` | 97.1% | 93.0% | 1,384 | 9,920 |
| `noisy_bal_s3_5x16x12x4` | 98.6% | 93.4% | 2,008 | 8,302 |
| `noisy_bal_s3_long_5x16x12x4` | 98.8% | 93.5% | 2,015 | 7,988 |
| `noisy_bal_s3_longB_5x16x12x4` | 98.8% | 93.5% | 1,926 | 8,084 |
| `noisy_bal_s3_longB_5x8x6x4` | 97.9% | 93.1% | 1,964 | 9,188 |
| `noisy_plain_s3_5x16x12x4` | 99.0% | 93.6% | 2,157 | 7,171 |
| `noisy_mid_s3_5x16x12x4` | 98.6% | 93.5% | 1,755 | 8,180 |
| `noisy_bal_5x16x12x4` | 98.2% | 93.4% | 2,028 | 8,072 |
| `noisy_bal_s3_5x8x6x4` | 98.3% | 93.3% | 1,968 | 8,720 |

All are noise-aware. Weighting for Unsafe-Hazardous / Caution samples: no tag = 4 / 2, `mid` = 3 / 1.75, `bal` = 2 / 1.5, `plain` = 1 / 1. `s3` = trained with 3-scan noise (like the firmware), `long`/`longB` = more data and epochs.

The installed model is `noisy_mid_s3_5x16x12x4`: compared with the earlier pick (`noisy_bal_s3_5x16x12x4`) it is more accurate overall *and* misses fewer dangerous samples.

### Round 4 (v4.1): could a network trained for adaptive scanning do better?

Eight more runs, all tested with adaptive re-scanning on realistic water (installed model: 94.6% correct, 1,508 dangerous missed):

| Candidate | Correct | Dangerous missed | False alarms |
| --- | --- | --- | --- |
| Same settings as installed, 3 new random starts (`mid_s3_r4`) | 94.5% | 1,724 | 7,184 |
| Trained on adaptive-scan readings, ×3 / ×1.75 weights (`mid_adapt`) | 94.6% | 1,744 | 6,471 |
| Trained on adaptive-scan readings, ×4 / ×2 weights (`adapt`) | 94.3% | 1,376 | 8,169 |

None beat the installed model on both counts, so its weights are unchanged. Training on the noisier 3-scan readings makes the network a little more careful near a limit, which still pays off when the firmware re-scans.

## Checks run on the installed model

- C engine (float32, as on the ESP32) vs Python on 100,000 random inputs: **0** different votes, **0** different final verdicts, largest probability difference 0.00005.
- Firmware simulation (stubbed ESP32 libraries, simulated voltammetry scans): 0 → Safe, 10 µg/L → Safe, 35 → Caution, 60 → Unsafe, 120 → Unsafe, 300 µg/L → Hazardous.
- Firmware re-scan rule: the C function from `esp32_firmware.ino` is compiled and checked against the Python rule on 3,000 readings.
- `python main.py --test`: 110 tests pass, including 9 for V3 (same weights everywhere, ESP32 size budget, rules never relaxed, C = Python on 3,000 inputs, firmware re-scan settings and rule match the training code).

## Limits — please read

- **All data is simulated.** The labels come from the BIS/WHO rules and the noise from the sensor specs in `standards.py`. Real accuracy is only known after testing on water samples measured by a lab.
- The firmware was checked with a desktop compiler and stub libraries, not on a physical ESP32 (the ESP32 toolchain could not be downloaded in the build environment). The first real flash should be watched on the Serial Monitor.
- If your electrode has different noise than `standards.py` says, retrain with the real figures: `Neural_Network/v3_training/README.md` explains how.
