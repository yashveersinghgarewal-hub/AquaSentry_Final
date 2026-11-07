"""Copy a model JSON and attach the independent test results from eval_v3.py output.
Usage: python3 add_test_metrics.py <model.json> <eval_scans1.json> <eval_scans3.json> <out.json>"""
import json, os, sys
src, e1, e3, out = sys.argv[1:]
d = json.load(open(src)); r1 = json.load(open(e1)); r3 = json.load(open(e3))
name = os.path.basename(src).replace("_best.json", "")
A = r3["A_exact_network_only"][name]
def e2e(r, key):
    return {"rules_only": r[key]["rules only"], "aquanet_v3": r[key][name]}
b3 = r3["B_noisy_end_to_end_realistic_water_scans3"]
miss_rules, miss_v3 = b3["rules only"]["dangerous_missed"], b3[name]["dangerous_missed"]
d["test"] = {
    "exact_accuracy_pct": round(A["field_like"]["accuracy_pct"], 1),
    "exact_accuracy_near_limits_pct": A["near_limits"]["accuracy_pct"],
    "end_to_end_accuracy_3_scans_pct": b3[name]["accuracy_pct"],
    "missed_dangerous_reduction_pct": round(100 * (miss_rules - miss_v3) / miss_rules, 1),
    "dangerous_called_safe": b3[name]["dangerous_called_safe"],
    "end_to_end_realistic_water_1_scan": e2e(r1, "B_noisy_end_to_end_realistic_water_scans1"),
    "end_to_end_realistic_water_3_scans": e2e(r3, "B_noisy_end_to_end_realistic_water_scans3"),
    "end_to_end_near_limits_3_scans": e2e(r3, "B_noisy_end_to_end_near_limits_scans3"),
    "note": "Synthetic test sets with sensor noise from app/standards.py. Real field/lab samples are still needed.",
}
d["model_name"] = "AquaNet-V3"; d["source_file"] = os.path.basename(src)
json.dump(d, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in d["test"].items() if not isinstance(v, dict)}, indent=1))
