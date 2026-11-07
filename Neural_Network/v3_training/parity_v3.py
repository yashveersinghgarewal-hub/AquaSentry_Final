"""C (float32, ESP32-style) vs Python (float64) parity for AquaNet-V3. Usage: parity_v3.py <weights.json> <c_dir> <nn_dir> <work>"""
import json, math, os, random, subprocess, sys
wpath, cdir, nndir, work = sys.argv[1:5]
sys.path.insert(0, nndir)
import aquanet_v3 as A
rng = random.Random(5)
rows = []
lims = {0: [0.010, 0.050, 0.150, 0.020], 1: [6.0, 6.5, 8.5, 9.0], 2: [1500, 2000], 3: [5, 10]}
for i in range(100000):
    r = [math.exp(rng.uniform(math.log(0.0002), math.log(0.6))), rng.uniform(4.6, 10.4), math.exp(rng.uniform(math.log(60), math.log(4900))),
         math.exp(rng.uniform(math.log(0.05), math.log(90))), rng.uniform(6, 44)]
    if i % 3 == 0:
        f = rng.randrange(4); t = rng.choice(lims[f]); r[f] = t * (1 + rng.uniform(-0.02, 0.02))
    if i % 997 == 0: r[rng.randrange(5)] = rng.choice([-1.0, 1e6, float("nan")])
    rows.append(r)
with open(os.path.join(work, "in.txt"), "w") as f:
    for r in rows: f.write(" ".join(repr(v) for v in r) + "\n")
harness = r'''
#include <stdio.h>
#include <math.h>
#include "aquanet_v3.h"
int main(void){ double a,b,c,d,e; while(scanf("%lf %lf %lf %lf %lf",&a,&b,&c,&d,&e)==5){
 aquanet_result_t r=aquanet_v3_predict((float)a,(float)b,(float)c,(float)d,(float)e);
 printf("%d %d %.6f %.6f %.6f %.6f\n",(int)r.raw_model_class,(int)r.predicted_class,r.probabilities[0],r.probabilities[1],r.probabilities[2],r.probabilities[3]);} return 0; }
'''
open(os.path.join(work, "h.c"), "w").write(harness)
nn_c = os.path.join(nndir, "aquanet_v1.c")
cmd = ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-I", cdir, "-I", nndir, os.path.join(work, "h.c"), os.path.join(cdir, "aquanet_v3.c"), nn_c, "-lm", "-o", os.path.join(work, "h")]
subprocess.run(cmd, check=True)
out = subprocess.run([os.path.join(work, "h")], stdin=open(os.path.join(work, "in.txt")), capture_output=True, text=True, check=True).stdout.split("\n")
C = ["Safe", "Caution", "Unsafe", "Hazardous"]
vote_mis = final_mis = 0; maxdp = 0.0; examples = []
for r, line in zip(rows, out):
    v, fcls, *ps = line.split()
    p = A.predict(*r, weights_path=os.path.abspath(wpath))
    if C[int(v)] != p["network_vote"]: vote_mis += 1; examples.append((r, C[int(v)], p["network_vote"]))
    if C[int(fcls)] != p["predicted_class"]: final_mis += 1
    if all(math.isfinite(x) for x in r):
        maxdp = max(maxdp, max(abs(float(a) - b / 100) for a, b in zip(ps, p["probabilities_pct"].values())))
print(json.dumps({"inputs": len(rows), "vote_mismatches": vote_mis, "final_verdict_mismatches": final_mis,
                  "max_probability_difference": round(maxdp, 5), "examples": examples[:3]}, indent=1))
