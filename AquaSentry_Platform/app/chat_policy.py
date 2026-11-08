"""
AquaSentry AI Chatbot Policy, Domain Intent Gate & Grounding Engine.

Implements server-side policy enforcement:
1. Intent Classification:
   - IN_SCOPE: Water quality, arsenic, contaminants, standards (WHO/BIS), robot hardware, readings interpretation.
   - OUT_OF_SCOPE: General chit-chat, non-water trivia, external programming.
   - EMERGENCY_TOXICOLOGY: Acute poison ingestion, medical symptoms -> immediate emergency referral.
   - INJECTION_ATTEMPT: Attempts to extract system prompts, API keys, or override safety constraints.
2. Grounding:
   - Injects actual database readings (or explicit empty state) so AI never fabricates numbers.
3. Polite Redirection:
   - Returns structured, courteous redirection for off-topic prompts.
"""

import re
from enum import Enum
from typing import Dict, Optional, Tuple


class ChatIntent(str, Enum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    EMERGENCY_TOXICOLOGY = "emergency_toxicology"
    INJECTION_ATTEMPT = "injection_attempt"


INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) (instructions|prompts)",
    r"(reveal|print|show|dump) (the )?(system prompt|api key|environment variables|\.env|secrets)",
    r"you are now (an unrestricted|in developer mode|jailbreak)",
    r"bypass (safety|guidelines|guardrails)",
    r"repeat the words above",
]

# Emergency poisoning and acute medical distress patterns
EMERGENCY_PATTERNS = [
    r"(swallowed|ingested|drank|drink).*(poison|arsenic|contaminat|toxic)",
    r"(vomiting|vomit).*(blood|severe|pain)",
    r"(acute|severe).*(poison|toxicity|poisoning)",
    r"(am i going to die|medical emergency)",
]

# Water safety and AquaSentry relevant keywords (word boundary enforced)
IN_SCOPE_WORDS = [
    r"\bwater\b", r"\barsenic\b", r"\basv\b", r"\bvoltammetry\b", r"\bmas-g1\b",
    r"\baquasentry\b", r"\breading\b", r"\breadings\b", r"\bsample\b", r"\bsamples\b",
    r"\bsensor\b", r"\bsensors\b", r"\bcontaminant\b", r"\bcontaminants\b",
    r"\blead\b", r"\bcadmium\b", r"\bmercury\b", r"\bchromium\b", r"\bfluoride\b",
    r"\bnitrate\b", r"\bwho (guideline|guidelines|standard|standards|limit|limits|potability)\b",
    r"\bworld health organization\b", r"\bbis\b", r"\bis 10500\b", r"\bpotability\b",
    r"\bpotable\b", r"\bdrinking\b", r"\bfilter\b", r"\bfiltration\b", r"\bppb\b",
    r"\bppm\b", r"\bµg/l\b", r"\bmg/l\b", r"\bph\b", r"\bturbidity\b",
    r"\bconductivity\b", r"\bcatamaran\b", r"\brobot\b", r"\baquanet\b", r"\bneural\b",
    r"\bsynapse\b", r"\bsynapses\b", r"\bcalibration\b", r"\blod\b", r"\bloq\b",
    r"\bdetection limit\b", r"\bicp-ms\b", r"\bhg-aas\b", r"\bro\b",
    r"\breverse osmosis\b", r"\btreatment\b", r"\bgroundwater\b", r"\bwell\b",
    r"\btubewell\b", r"\bendpoint\b", r"\bfastapi\b",
]


def classify_user_prompt(message: str) -> Tuple[ChatIntent, Optional[str]]:
    """
    Classify incoming user chat message before sending to LLM.
    Returns (ChatIntent, optional_preformatted_response).
    """
    cleaned = message.strip().lower()

    # 1. Prompt Injection Check
    for pat in INJECTION_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return (
                ChatIntent.INJECTION_ATTEMPT,
                "🔒 **Security Notice:** AquaSentry Assistant operates under strict scientific and public-health "
                "guardrails. System instructions, environment credentials, and safety policies cannot be bypassed or disclosed."
            )

    # 2. Emergency Medical / Acute Exposure Check
    for pat in EMERGENCY_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return (
                ChatIntent.EMERGENCY_TOXICOLOGY,
                "🚨 **URGENT PUBLIC HEALTH NOTICE:**\n\n"
                "If you or someone else has ingested severely contaminated water or is experiencing acute symptoms "
                "(severe abdominal pain, persistent vomiting, or symptoms of acute poisoning), **please seek immediate medical attention or contact your local emergency services / poison control center.**\n\n"
                "AquaSentry is an autonomous environmental screening prototype and **does not provide emergency medical diagnosis or treatment.**"
            )

    # 3. In-Scope Domain Check (Word Boundary matching)
    for pat in IN_SCOPE_WORDS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return (ChatIntent.IN_SCOPE, None)

    # Short greetings are in-scope
    if cleaned in ["hi", "hello", "hey", "help", "who are you", "what can you do"]:
        return (ChatIntent.IN_SCOPE, None)

    # 4. Out-of-Scope Fallback
    return (
        ChatIntent.OUT_OF_SCOPE,
        "💧 **AquaSentry Water Quality Assistant:**\n\n"
        "I specialize strictly in water safety, heavy metal contaminants (such as arsenic, lead, and cadmium), "
        "drinking water standards (WHO / BIS 10500), sensor voltammetry, and AquaSentry robot diagnostics.\n\n"
        "How can I help you regarding water quality monitoring, sample interpretation, or this project?"
    )


def format_grounded_context(latest_reading: Optional[Dict]) -> str:
    """Format live database reading context for insertion into LLM system prompt."""
    if not latest_reading:
        return (
            "\nCURRENT DATABASE CONTEXT:\n"
            "- System State: Initial Empty State (No readings recorded yet).\n"
            "- Notice: Inform the user that no water samples have been captured yet, and guide them to "
            "connect a device, load demo data, or import a CSV file.\n"
        )

    as_ppb = latest_reading.get("arsenic_ppb", "N/A")
    as_mg_l = latest_reading.get("arsenic_mg_l", "N/A")
    status = latest_reading.get("analytical_status", "N/A")
    tier = latest_reading.get("regulatory_tier", "N/A")
    src = latest_reading.get("source_type", "simulated")
    ts = latest_reading.get("recorded_at", "Just now")
    device = latest_reading.get("device_code", "AQUA-001")

    return (
        f"\nCURRENT DATABASE CONTEXT (Ground Truth):\n"
        f"- Device: {device}\n"
        f"- Timestamp: {ts}\n"
        f"- Arsenic Concentration: {as_ppb} µg/L ({as_mg_l} mg/L)\n"
        f"- Analytical Status: {status}\n"
        f"- Regulatory Tier: {tier}\n"
        f"- Source Type: {src} (Marked {'DEMO/SIMULATED' if src != 'hardware' else 'PHYSICAL HARDWARE'})\n"
        f"- Safe to Drink: {latest_reading.get('is_safe_to_drink', 'Unverified')}\n"
        f"- Precedence Notice: Method LOD is 20 µg/L. If concentration < 20 µg/L, it CANNOT be confirmed potable without lab testing.\n"
    )


def format_fleet_context(devices) -> str:
    """Per-device status and arsenic trend lines for the system prompt (hardware nodes first, max 10)."""
    if not devices:
        return ""
    lines = ["\nFLEET CONTEXT (one line per sensor node):"]
    for d in devices[:10]:
        latest = d.get("latest") or {}
        t = d.get("trend") or {}
        bits = [f"- {d['device_code']}: {d.get('status', 'unknown')}"]
        if latest:
            bits.append(f"latest {latest.get('arsenic_ppb')} µg/L ({latest.get('classification')})")
        if t.get("direction") in ("rising", "falling"):
            bits.append(f"trend {t['direction']} ({t.get('message', '')})")
        lines.append(", ".join(bits))
    return "\n".join(lines) + "\n"


_ASK_LIMIT = re.compile(r"\b(limit|limits|standard|standards|guideline|permissible|bis|is 10500|lod|detection)\b", re.I)
_ASK_TREND = re.compile(r"\b(trend|rising|increas\w*|worse|getting|over time|falling|decreas\w*)\b", re.I)
_ASK_FLEET = re.compile(r"\b(device|devices|node|nodes|offline|online|fleet|sensor|sensors)\b", re.I)
_ASK_LATEST = re.compile(r"\b(latest|last|current|now|today|reading|result|safe|drink|my water)\b", re.I)


def offline_answer(message: str, latest: Optional[Dict], devices) -> str:
    """Grounded answers without an LLM, for a field laptop with no internet or no GEMINI_API_KEY.
    Every number comes from the database or the standards module; nothing is generated."""
    parts = []
    if _ASK_LIMIT.search(message):
        parts.append("**Limits:** arsenic must stay below **10 µg/L** in drinking water (India IS 10500:2012 "
                     "Amendment 1, no relaxation; WHO guideline). This sensor detects arsenic from **20 µg/L**, so "
                     "a result below that is *not detected*, not *proven safe*: only a laboratory test (ICP-MS or "
                     "HG-AAS) can confirm water is under 10 µg/L.")
    if _ASK_TREND.search(message):
        moving = [d for d in (devices or []) if (d.get("trend") or {}).get("direction") in ("rising", "falling")]
        if moving:
            parts.append("**Trends:**\n" + "\n".join(f"- {d['device_code']}: {d['trend']['message']}" for d in moving))
        else:
            parts.append("**Trends:** no node shows a statistically clear rising or falling arsenic trend "
                         "(Mann-Kendall test, p < 0.10, needs at least 6 readings).")
    if _ASK_FLEET.search(message) and devices:
        counts = {}
        for d in devices:
            counts[d.get("status", "unknown")] = counts.get(d.get("status", "unknown"), 0) + 1
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        quiet = [d["device_code"] for d in devices if d.get("status") == "offline"]
        parts.append(f"**Nodes:** {len(devices)} ({summary})." + (f" Not reporting: {', '.join(quiet)}." if quiet else ""))
    if _ASK_LATEST.search(message) or not parts:
        if latest:
            where = f" at **{latest.get('device_code')}**" if latest.get("device_code") else ""
            demo = " This is demo / simulated data." if latest.get("source_type") != "hardware" else ""
            parts.append(f"**Latest reading{where}:** {latest.get('arsenic_ppb')} µg/L, "
                         f"{latest.get('analytical_status')} ({latest.get('regulatory_tier')}).{demo}")
        else:
            parts.append("**No readings yet.** Connect a node, load the demo data or import a CSV file.")
    parts.append("_Offline answer from your own data. Add GEMINI_API_KEY in .env for free-form questions._")
    return "\n\n".join(parts)
