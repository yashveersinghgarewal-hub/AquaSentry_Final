"""
Measurement-quality flags attached to readings (v5.6). They never change the verdict engines (the four
rule copies stay in parity); they say when a result needs more caution than its number suggests.

- as3_only: the node measured raw water without the acid / reducing electrolyte. As(V), the other common
  form of arsenic in groundwater, is electrochemically inactive in that case, so the node can under-read.
  A "No arsenic detected" from such a node cannot rule arsenic out.
- copper_interference: copper strips near arsenic on gold electrodes and forms Cu-As intermetallics
  that suppress the arsenic peak. Flagged when the copper peak is large next to the arsenic peak.
- uncalibrated: the node used the factory calibration, not one made for its own electrode.
"""
from __future__ import annotations

import os
from typing import List, Optional

CAVEATS = {
    "as3_only": "This node measures As(III) only; As(V) is not seen without the acid electrolyte step, "
                "so the result can be too low. Confirm with a laboratory test.",
    "copper_interference": "A large copper signal was found; copper can hide arsenic. Confirm with a laboratory test.",
    "uncalibrated": "The node used the factory calibration, not one made for its electrode.",
}


def copper_ratio() -> float:
    return float(os.getenv("COPPER_FLAG_RATIO", "3"))


def qc_flags(species: Optional[str], peak_ua: Optional[float], cu_peak_ua: Optional[float],
             calibration_ref: Optional[str], source_type: Optional[str]) -> List[str]:
    flags = []
    if source_type == "hardware":
        if species == "as3_only":
            flags.append("as3_only")
        if cu_peak_ua is not None and cu_peak_ua > 0:
            base = max(peak_ua or 0.0, 0.05)          # 0.05 µA: about the noise floor of a single scan
            if cu_peak_ua >= copper_ratio() * base:
                flags.append("copper_interference")
        if not calibration_ref:
            flags.append("uncalibrated")
    return flags


def caveats(flags_csv: Optional[str]) -> List[str]:
    return [CAVEATS[f] for f in (flags_csv or "").split(",") if f in CAVEATS]
