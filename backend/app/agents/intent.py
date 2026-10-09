"""
Intent classification for hotel guest messages.

Returns one of 17 standardized intent categories using LLM + keyword fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Intent Registry ──────────────────────────────────────────────────────────

class Intent:
    HOTEL_INFO = "HOTEL_INFO"
    BOOKING = "BOOKING"
    CHECK_IN_CHECKOUT = "CHECK_IN_CHECKOUT"
    ROOM_INFORMATION = "ROOM_INFORMATION"
    HOUSEKEEPING = "HOUSEKEEPING"
    MAINTENANCE = "MAINTENANCE"
    DINING = "DINING"
    FACILITIES = "FACILITIES"
    TRANSPORTATION = "TRANSPORTATION"
    CONCIERGE = "CONCIERGE"
    COMPLAINT = "COMPLAINT"
    BILLING = "BILLING"
    LOST_FOUND = "LOST_FOUND"
    ACCESSIBILITY = "ACCESSIBILITY"
    EMERGENCY = "EMERGENCY"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    GENERAL = "GENERAL"


# ─── Keyword Rules (fast path) ────────────────────────────────────────────────

_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    (Intent.EMERGENCY, [
        r"\bfire\b", r"\bmedical emergency\b", r"\bcardiac\b", r"\bunconscious\b",
        r"\bambulance\b", r"\bcall 911\b", r"\bemergency\b", r"\bintruder\b",
        r"\blife threatening\b", r"\bsevere injury\b",
    ]),
    (Intent.HUMAN_ESCALATION, [
        r"\bfront desk\b", r"\bspeak to\b", r"\btalk to\b", r"\bhuman\b",
        r"\bmanager\b", r"\bstaff\b", r"\breal person\b", r"\bdon't want to talk to.*bot\b",
        r"\bsecurity\b", r"\bhallway\b", r"\bhotel management\b", r"\bconnect me with\b",
    ]),
    (Intent.LOST_FOUND, [
        r"\blost\b", r"\bfound\b", r"\bmissing\b", r"\bforgot\b", r"\bleft my\b",
    ]),
    (Intent.ACCESSIBILITY, [
        r"\bwheelchair\b", r"\bdisabilit", r"\baccessib", r"\bhandicap\b", r"\broll.in shower\b",
    ]),
    (Intent.BILLING, [
        r"\bbill\b", r"\binvoice\b", r"\bcharge\b", r"\bpayment\b",
        r"\bfolio\b", r"\breceipt\b", r"\bextra charge\b",
    ]),
    (Intent.COMPLAINT, [
        r"\bcomplaint\b", r"\bdisappoint", r"\bdissatisfied\b", r"\bunhappy\b",
        r"\bterrible\b", r"\bawful\b", r"\bhorrific\b", r"\bworse\b",
        r"\bloud music\b", r"\btoo loud\b", r"\bnoisy\b", r"\bdirty\b", r"\bnot cleaned\b",
    ]),
    (Intent.MAINTENANCE, [
        r"\bbroken\b", r"\bnot working\b", r"\bmaintenance\b", r"\b\bac\b\b",
        r"\bair condition", r"\bleaking\b", r"\bplumbing\b", r"\belectricity\b",
        r"\btv\b.*\bwork", r"\binternet.*work", r"\blight.*work",
        r"\bkeycard\b", r"\bkey card\b", r"\btoilet\b", r"\bflush\b", r"\bclogged\b",
        r"\bhot water\b", r"\bac hot\b", r"\bac not cold\b", r"\bstopped working\b",
        r"\bjammed\b", r"\bwon't unlock\b", r"\bunlock\b", r"\bflicker", r"\bbulb\b",
        r"\bsafe\b",
    ]),
    (Intent.HOUSEKEEPING, [
        r"\b(?:towels?|blankets?|pillows?|shampoos?|soaps?|toiletries|irons?|waters?|ice bucket|bag of ice|hangers?|sheets?|robes?|slippers?|dental kits?|shaving kits?)\b",
        r"\bhousekeeping\b", r"\bclean(?:ing)?\b",
        r"\b(?:bring|send|deliver(?:ed)?|get)\s+(?:extra\s+)?(?:towels?|pillows?|blankets?|beds?|sheets?|shampoos?|soaps?|toiletries|hangers?|waters?|ice|amenit)",
    ]),
    (Intent.CHECK_IN_CHECKOUT, [
        r"\bcheck.in\b", r"\bcheck.out\b", r"\bearly check\b", r"\blate check\b",
        r"\bcheckout\b", r"\bcheckin\b", r"\bcheck in time\b", r"\bcheck out time\b",
        r"\bleaving early\b", r"\bearly departure\b", r"\bluggage\b", r"\bflight\b",
        r"\bdocuments?\b", r"\bid required\b", r"\bpassport\b", r"\bcheck in on\b", r"\bcheck in at\b",
    ]),
    (Intent.DINING, [
        r"\bbreakfast\b", r"\blunch\b", r"\bdinner\b", r"\brestaurant\b",
        r"\bfood\b", r"\bmenu\b", r"\bdine\b", r"\bdining\b",
        r"\bbuffet\b", r"\broom service\b", r"\bbar\b", r"\bcuisine\b",
        r"\bvegetarian\b", r"\bvegan\b", r"\bspicy\b", r"\blight meal\b",
        r"\bsnack\b", r"\btapas\b", r"\bsurprise.*restaurant\b", r"\beating\b",
        r"\bcomplimentary\b", r"\bcomplimentory\b", r"\bcpmlimentory\b",
        r"\bfree food\b", r"\bmeals?\b",
    ]),
    (Intent.TRANSPORTATION, [
        r"\bairport\b", r"\btransfer\b", r"\btaxi\b", r"\bcab\b",
        r"\bshuttle\b", r"\bcar\b", r"\bparking\b", r"\bvalet\b",
        r"\buber\b", r"\blyft\b", r"\bdrop.*off\b",
    ]),
    (Intent.FACILITIES, [
        r"\bpool\b", r"\bgym\b", r"\bspa\b", r"\bfitness\b",
        r"\bbusiness center\b", r"\bconference\b", r"\bamenit",
        r"\bcorporate\b", r"\bparty\b", r"\bparties\b", r"\bbanquet\b", r"\bevent\b",
        r"\bteam\b", r"\bclient\b", r"\bmeeting\b", r"\bmeet\b", r"\blounge\b",
    ]),
    (Intent.BOOKING, [
        r"\bbook\s+(?:a\s+)?(?:room|stay|suite|table|reservation|night)\b",
        r"\breserv", r"\bcancell?\b", r"\bmodify.*reservation\b",
        r"\bavailability\b", r"\boffers?\b", r"\bdiscount\b", r"\bpromotions?\b",
        r"\bdeals?\b", r"\bpackages?\b",
    ]),
    (Intent.CONCIERGE, [
        r"\brecommend\b", r"\bthings to do\b", r"\btourist\b", r"\bsightseeing\b",
        r"\bdestination", r"\bshow\b", r"\brestaurant.*nearby\b", r"\blocal\b",
        r"\bpolice station\b", r"\bhospital\b", r"\bpharmacy\b", r"\bfirst time\b",
        r"\bparents\b", r"\bfamily\b", r"\bfree evening\b", r"\b3 hours\b", r"\bhours\b",
        r"\bvisit\b", r"\bouting\b", r"\bwhere to go\b", r"\bcoming over\b",
    ]),
    (Intent.HOTEL_INFO, [
        r"\breception\b", r"\bcontact number\b", r"\bphone number\b",
        r"\boperator\b", r"\bhotel number\b", r"\bhow to call\b",
        r"\bpet\b", r"\bdog\b", r"\bcat\b", r"\banimal\b", r"\btiger\b", r"\bsnake\b",
        r"\bwifi\b", r"\bwi-fi\b", r"\binternet\b", r"\bpassword\b",
        r"\belectric vehicle\b", r"\bev\b", r"\bcharger\b", r"\bcharging\b", r"\btesla\b",
    ]),
    (Intent.ROOM_INFORMATION, [
        r"\broom\b.*\btype\b", r"\broom\b.*\bfeature", r"\bview\b",
        r"\bsuite\b", r"\bwhat.*room\b",
    ]),
]


@dataclass
class ClassificationResult:
    intent: str
    sub_intent: str
    confidence: float


def _keyword_classify(text: str) -> ClassificationResult | None:
    """Fast keyword-based classification as first-pass filter."""
    text_lower = text.lower()
    for intent, patterns in _KEYWORD_RULES:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                logger.debug("keyword_intent_match", intent=intent, pattern=pattern)
                return ClassificationResult(
                    intent=intent,
                    sub_intent="",
                    confidence=0.85,
                )
    return None


# LLM classification prompt
_CLASSIFICATION_PROMPT = """You are an intent classifier for a hotel guest assistant.

Classify the guest message into EXACTLY ONE intent from this list:
HOTEL_INFO, BOOKING, CHECK_IN_CHECKOUT, ROOM_INFORMATION, HOUSEKEEPING,
MAINTENANCE, DINING, FACILITIES, TRANSPORTATION, CONCIERGE, COMPLAINT,
BILLING, LOST_FOUND, ACCESSIBILITY, EMERGENCY, HUMAN_ESCALATION, GENERAL

Rules:
- EMERGENCY: fire, medical emergency, police needed
- HUMAN_ESCALATION: guest explicitly wants human/front desk/manager
- HOUSEKEEPING: towels, cleaning, extra items for room
- MAINTENANCE: broken equipment, not working, repair needed
- COMPLAINT: expressing dissatisfaction, disappointment
- GENERAL: anything that doesn't clearly fit other categories

Respond with ONLY this JSON format (no other text):
{"intent": "INTENT_NAME", "sub_intent": "brief description", "confidence": 0.95}

Guest message: {message}"""


def classify_intent(message: str, use_llm: bool = True) -> ClassificationResult:
    """
    Classify guest message intent.

    Strategy:
    1. Emergency keyword check (always LLM-free for speed)
    2. Keyword rules for common intents
    3. LLM classification for ambiguous cases
    """
    # Always catch emergencies first
    emergency_patterns = [r"\bfire\b", r"\bmedical emergency\b", r"\bambulance\b"]
    msg_lower = message.lower()
    for p in emergency_patterns:
        if re.search(p, msg_lower):
            return ClassificationResult(
                intent=Intent.EMERGENCY,
                sub_intent="emergency",
                confidence=1.0,
            )

    # Keyword fast path
    keyword_result = _keyword_classify(message)
    if keyword_result and keyword_result.confidence >= 0.85:
        return keyword_result

    # LLM classification for ambiguous
    if use_llm:
        try:
            llm = get_llm()
            prompt = _CLASSIFICATION_PROMPT.format(message=message)
            response = llm.invoke([
                SystemMessage(content="You are a hotel intent classifier. Respond only with JSON."),
                HumanMessage(content=prompt),
            ])
            content = response.content if hasattr(response, "content") else str(response)

            import json
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ClassificationResult(
                    intent=data.get("intent", Intent.GENERAL),
                    sub_intent=data.get("sub_intent", ""),
                    confidence=float(data.get("confidence", 0.7)),
                )
        except Exception as e:
            logger.error("llm_classification_failed", error=str(e))

    # Fallback to keyword or GENERAL
    return keyword_result or ClassificationResult(
        intent=Intent.GENERAL,
        sub_intent="",
        confidence=0.5,
    )
