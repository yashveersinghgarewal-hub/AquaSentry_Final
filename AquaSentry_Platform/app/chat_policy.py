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
from typing import Dict, List, Optional, Tuple


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
