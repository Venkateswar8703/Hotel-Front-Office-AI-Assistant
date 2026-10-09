"""
LLM provider factory — returns a LangChain BaseChatModel based on config.
Supports: mock (default), Google Gemini, Amazon Bedrock.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.core.config import LLMProvider, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ─── Mock LLM for local development ──────────────────────────────────────────

class MockChatModel(BaseChatModel):
    """
    A deterministic mock LLM that returns sensible canned responses.
    Used when LLM_PROVIDER=mock (default) so the app runs without API keys.
    """

    model_name: str = "mock-hotel-concierge-v1"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        import re

        # Check if system message contains retrieved RAG context
        system_text = ""
        for m in messages:
            if isinstance(m, SystemMessage):
                system_text = str(m.content)
                break

        last_human = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
            "",
        )

        # 1. If RAG system prompt is present, respect context grounding strictly
        if system_text and "CONTEXT PROVIDED:" in system_text:
            context_part = system_text.split("CONTEXT PROVIDED:", 1)[1].strip()
            if not context_part or "No relevant context found" in context_part:
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(
                        content="I could not find verified hotel policy information on this in the knowledge base. Please check the property management system (PMS) or consult the Duty Manager."
                    ))]
                )

            human_lower = str(last_human).lower()
            is_checkin = any(w in human_lower for w in ["checkin", "check-in", "check in"])
            is_checkout = any(w in human_lower for w in ["checkout", "check-out", "check out"])

            # If query asks about both check-in and check-out, synthesize both answers from context
            if is_checkin and is_checkout:
                in_matches = re.finditer(r'Q:[^\n]*check-?in[^\n]*\n\s*A:\s*([^\n\r]+(?:\n(?!\s*(?:\[\d+\]|\(Relevance|\(Source|Category:|Q:))[^\n\r]+)*)', context_part, re.IGNORECASE)
                out_matches = re.finditer(r'Q:[^\n]*check-?out[^\n]*\n\s*A:\s*([^\n\r]+(?:\n(?!\s*(?:\[\d+\]|\(Relevance|\(Source|Category:|Q:))[^\n\r]+)*)', context_part, re.IGNORECASE)
                ans_in = next((m.group(1).strip() for m in in_matches if not any(p in m.group(1).lower() for p in ["the assistant should", "is determined by the hotel"])), "Standard check-in time is 3:00 PM. Early check-in is subject to availability.")
                ans_out = next((m.group(1).strip() for m in out_matches if not any(p in m.group(1).lower() for p in ["the assistant should", "is determined by the hotel"])), "Standard check-out time is 12:00 PM (noon). Late check-out until 2:00 PM may be requested at the front desk.")
                combined = f"• **Check-In Policy**: {ans_in}\n• **Check-Out Policy**: {ans_out}"
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=combined))]
                )

            # If query asks about front desk / reception hours:
            if any(w in human_lower for w in ["front desk", "reception", "open all the time", "allthe time", "open 24 hours", "24/7", "what time reception"]):
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(
                        content=(
                            "**Front Desk & Hotel Operating Hours:**\n"
                            "• The hotel and Front Desk / Reception are open and staffed **24 hours a day, 7 days a week**.\n"
                            "• Late check-in, guest assistance, and concierge services are available at all times in the main lobby or by dialing Ext **0**."
                        )
                    ))]
                )

            # Match question and answer blocks together
            all_matches = re.finditer(
                r'Q:\s*([^\n\r]+)\n\s*A:\s*([^\n\r]+(?:\n(?!\s*(?:\[\d+\]|\(Relevance|\(Source|Category:|Q:))[^\n\r]+)*)',
                context_part,
                re.IGNORECASE,
            )
            human_words = set(re.findall(r'\b\w+\b', human_lower))
            for m in all_matches:
                cand_q = m.group(1).strip().lower()
                cand = m.group(2).strip()
                cand_q_words = set(re.findall(r'\b\w+\b', cand_q))
                overlap = len(human_words & cand_q_words) / max(len(cand_q_words), 1)

                cand_is_placeholder = any(
                    phrase in cand.lower()
                    for phrase in [
                        "the assistant should",
                        "the assistant can",
                        "rates and offers can vary by dates, room type",
                        "is determined by the hotel and is provided during the booking process",
                        "certainly. i can create a personalized recommendation",
                    ]
                )
                if cand and len(cand) > 5 and not cand_is_placeholder and (overlap > 0.20 or len(human_words & cand_q_words) >= 1):
                    return ChatResult(
                        generations=[ChatGeneration(message=AIMessage(content=cand))]
                    )

            # Fallback to specific factual canned response if available for this topic
            mock_ans = self._mock_response(str(last_human))
            if "I could not find verified hotel policy information" not in mock_ans:
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=mock_ans))]
                )

            # If no specific mock answer, try non-placeholder block from context
            first_block = context_part.split("\n\n")[0].strip()
            cleaned_block = re.sub(r'^\[\d+\][^\n]*\n', '', first_block)
            cleaned_block = re.sub(r'^\s*Category:[^\n]*\n', '', cleaned_block)
            cleaned_block = re.sub(r'^\s*Q:[^\n]*\n\s*A:\s*', '', cleaned_block)
            cleaned_block = re.sub(r'\s*\(Relevance:[^\)]+\)', '', cleaned_block).strip()

            is_block_placeholder = any(
                phrase in cleaned_block.lower()
                for phrase in [
                    "the assistant should",
                    "the assistant can",
                    "rates and offers can vary by dates, room type",
                    "is determined by the hotel and is provided during the booking process",
                    "certainly. i can create a personalized recommendation",
                ]
            )

            if cleaned_block and len(cleaned_block) > 5 and not is_block_placeholder:
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=cleaned_block))]
                )

            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(
                    content="I could not find verified hotel policy information on this in the knowledge base. Please check the property management system (PMS) or consult the Duty Manager."
                ))]
            )

        # 2. Otherwise use query-specific mock generator
        response_text = self._mock_response(str(last_human))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=response_text))]
        )

    def _mock_response(self, user_input: str) -> str:
        import re
        lower = user_input.lower().strip()

        # 1. Greetings & Shift Start
        if any(w in lower for w in ["checked into", "just arrived", "checking in"]) or lower in ["hi", "hello", "hey", "good morning", "good evening", "good afternoon", "greetings"]:
            return (
                "Hello! Front Office AI Copilot is online and ready to assist your shift. "
                "You can query hotel policies, look up amenities/timings, check VIP procedures, or dispatch housekeeping and engineering tickets."
            )

        # Front Desk & Hotel Operating Hours / 24-Hour Services
        if any(w in lower for w in ["open all the time", "allthe time", "open 24 hours", "24/7", "front desk hours", "reception hours", "reception open", "desk open", "is hotel open", "what time reception"]):
            return (
                "**Front Desk & Hotel Operating Hours:**\n"
                "• The hotel and Front Desk / Reception are open and staffed **24 hours a day, 7 days a week**.\n"
                "• Late check-in, guest assistance, and concierge services are available at all times in the main lobby or by dialing Ext **0**."
            )

        # Guest Name / Profile lookup
        if any(w in lower for w in ["name of me", "who am i", "my name", "what is my name"]):
            return (
                "No guest profile is currently registered to this session. "
                "Please provide your Room Number or Reservation Name if you would like me to look up your stay details."
            )

        # Check-in / Check-out specific
        if any(w in lower for w in ["check out", "checkout", "check-out"]):
            return (
                "**Check-Out Policy:**\n"
                "• Standard check-out time is **12:00 PM (noon)**.\n"
                "• Late check-out may be requested at the front desk (subject to availability; fees may apply after 1:00 PM)."
            )
        if any(w in lower for w in ["check in", "checkin", "check-in"]):
            return (
                "**Check-In Policy:**\n"
                "• Standard check-in time is **3:00 PM**.\n"
                "• Early check-in is subject to room availability upon arrival."
            )

        # Wi-Fi details
        if "wifi" in lower or "wi-fi" in lower or "internet" in lower or "network" in lower:
            return (
                "**Guest Wi-Fi Details:**\n"
                "• Network: `HotelGuest` | Password: `Welcome2024` (or Room Number + Last Name login portal).\n"
                "• Front desk / Staff network: `HotelStaff_Secure` (WPA3 Enterprise)."
            )

        # Pet policy
        if "pet" in lower or "dog" in lower or "cat" in lower:
            return (
                "**Pet Policy:**\n"
                "• Dogs and cats up to 50 lbs permitted (maximum 2 pets per room).\n"
                "• Pet fee: $75 non-refundable cleaning fee per stay (service animals exempt).\n"
                "• Welcome pet amenity pack provided at check-in."
            )

        # Parking and EV charging
        if "parking" in lower or "ev charging" in lower or "charger" in lower or "valet" in lower:
            return (
                "**Parking & EV Policy:**\n"
                "• Valet Overnight: $45/night with unlimited in-and-out privileges.\n"
                "• Self-parking: $30/night in adjacent secure garage.\n"
                "• EV Charging: 8 Level-2 chargers + 2 Tesla Superchargers (Complimentary for hotel guests)."
            )

        # 2. Reception & Contact Info
        if any(w in lower for w in ["reception", "contact number", "phone number", "hotel number", "operator", "call reception", "call front desk", "extension"]):
            return (
                "**Front Office & Department Extensions:**\n"
                "• Front Desk / Operator: Ext **0** / direct (+1 800 555-4683)\n"
                "• Housekeeping Dispatch: Ext **3**\n"
                "• Engineering / Maintenance: Ext **4**\n"
                "• In-Room Dining / Kitchen: Ext **5**\n"
                "• Duty Manager / Security: Ext **9**"
            )

        # 3. Cryptocurrency / Gold payment & Billing Guidelines
        if any(w in lower for w in ["bitcoin", "ethereum", "crypto", "gold", "cryptocurrency"]):
            return (
                "**Accepted Payment Methods:**\n"
                "• Accepted: Major Credit/Debit Cards (Visa, MasterCard, Amex, Discover, JCB) and cash at check-out.\n"
                "• Not Accepted: Cryptocurrencies (Bitcoin, Ethereum) and commodity payments are not accepted."
            )

        if any(w in lower for w in ["bill", "folio", "invoice", "charge", "receipt"]):
            return (
                "**Front Desk Billing & Folio Guidelines:**\n"
                "• Incidental hold: $50/night for card pre-authorizations (released within 3-5 business days upon checkout).\n"
                "• Direct billing / City Ledger accounts require approved corporate credit application on file.\n"
                "• Split billing can be configured in PMS under Folio Routing (Windows 1-4)."
            )

        # 4. Lost & Found Procedure
        if any(w in lower for w in ["lost", "found", "left my", "missing item"]):
            return (
                "**Lost & Found Operational Procedure:**\n"
                "1. Check the 24/7 Lost & Found registry log in the front office cabinet.\n"
                "2. High-value items (wallets, jewelry, electronics) are secured in the Front Desk Manager safe.\n"
                "3. Record guest contact info, item details, room number, and logging staff ID."
            )

        # 5. Accessibility
        if any(w in lower for w in ["wheelchair", "accessible", "accessibility", "handicap", "roll-in"]):
            return (
                "**ADA & Accessibility Amenities:**\n"
                "• Property features step-free main entrance, automated doors, and 4 high-speed accessible elevators.\n"
                "• 12 ADA-compliant accessible rooms with roll-in showers, lower fixtures, and emergency pull cords.\n"
                "• Pool lift available on Level 5 terrace; hearing-impaired TTY kits available at front desk."
            )

        # Luggage storage policy
        if "luggage" in lower or "baggage" in lower or "store bags" in lower:
            return (
                "**Luggage Storage Policy:**\n"
                "• Complimentary secure luggage storage is available 24/7 at the Bell Desk before check-in and after check-out.\n"
                "• Luggage claim tags are issued upon deposit; items can be stored for up to 24 hours on day of departure."
            )

        # Extra bed / Crib policy
        if "extra bed" in lower or "rollaway" in lower or "crib" in lower or "cot" in lower or "beds and crib" in lower:
            return (
                "**Extra Beds & Cribs Policy:**\n"
                "• Rollaway extra beds: $35/night (available for King and Suite categories; maximum 1 extra bed per room).\n"
                "• Baby cribs / pack-and-plays: Complimentary upon request (subject to availability)."
            )

        # Cancellation policy
        if "cancell" in lower:
            return (
                "**Cancellation Policy:**\n"
                "• Flexible reservations: Free cancellation up to 48 hours prior to 3:00 PM on arrival date.\n"
                "• Late cancellations or no-shows are subject to a fee equal to the first night's room and tax."
            )

        # Cryptocurrency / Gold payment
        if any(w in lower for w in ["bitcoin", "ethereum", "crypto", "gold", "cryptocurrency"]):
            return (
                "**Accepted Payment Methods:**\n"
                "• Accepted: Major Credit/Debit Cards (Visa, MasterCard, Amex, Discover, JCB) and cash at check-out.\n"
                "• Not Accepted: Cryptocurrencies (Bitcoin, Ethereum) and commodity payments are not accepted."
            )

        # 6. Early departure / Express checkout
        if any(w in lower for w in ["leaving early", "early departure", "flight", "luggage", "arrange tonight"]):
            return (
                "**Early Departure / Express Checkout Protocol:**\n"
                "1. Inform guest of early departure fee ($50) if booked under non-flexible group/corporate rate unless waived by manager.\n"
                "2. Offer Grab-and-Go breakfast box (ready at 5:00 AM upon night audit request).\n"
                "3. Pre-book taxi / airport transport via Concierge dispatch.\n"
                "4. Settle folio charges before 11:00 PM night audit run."
            )

        # 7. Meeting & Visitor Policy
        if any(w in lower for w in ["meet me", "friend is visiting", "guest coming over", "meet someone", "meeting spot"]):
            return (
                "**Visitor Policy & Public Spaces:**\n"
                "• Visitors are permitted in Lobby Lounge, Coffee Bar, and Rooftop Terrace until 11:00 PM.\n"
                "• Unregistered overnight visitors in guest rooms must be registered at the Front Desk with valid photo ID in accordance with local regulations."
            )

        # Fire, hazardous, or prohibited activity on balconies/in rooms
        if any(w in lower for w in ["barbecue", "bonfire", "grill", "charcoal", "gasoline", "fire on balcony", "open flame"]):
            return (
                "**Fire Safety & Balcony Policy:**\n"
                "• Open flames, charcoal grills, barbecues, and combustible materials are strictly prohibited in all guest rooms and balconies under municipal fire codes.\n"
                "• Violations will trigger automated fire alarms and incur emergency safety penalties."
            )

        # 8. Dining Hours & Dietary Info
        if any(w in lower for w in ["menu", "food suggestion", "cuisine", "light", "snack", "tapas", "vegetarian", "vegan", "spicy", "not spicy"]):
            return (
                "**F&B Information & Hours:**\n"
                "• **Grand Dining Room**: Breakfast (6:30 AM – 10:30 AM M-F, 7:00 AM – 11:00 AM Weekends), Lunch (12:00 PM – 2:30 PM), Dinner (6:00 PM – 10:30 PM).\n"
                "• **Rooftop Lounge (12th Floor)**: 4:00 PM – 1:00 AM daily.\n"
                "• **In-Room Dining**: 24/7 service (Late night menu active 11:00 PM – 6:00 AM).\n"
                "• Vegetarian, Vegan, Gluten-free, and Halal options clearly flagged on kitchen order system."
            )

        # 9. Housekeeping Dispatch
        if any(w in lower for w in ["towel", "pillow", "blanket", "housekeeping", "amenities", "soap", "shampoo"]):
            return (
                "Housekeeping dispatch logged. Our housekeeping team fulfills room amenity deliveries within 15 minutes."
            )

        # 10. Maintenance Dispatch
        if (
            re.search(r"\bac\b|\btv\b", lower)
            or any(w in lower for w in ["air condition", "heating", "broken", "not working", "maintenance", "leak", "plumbing", "toilet"])
        ):
            return (
                "Engineering work order logged. Standard response time is 30 minutes (10 minutes for urgent issues like plumbing leaks or electrical faults)."
            )

        # 11. Check-in Documents, Offers, Late Arrival
        if any(w in lower for w in ["document", "id required", "offer", "discount", "promotion", "package", "deal", "6pm", "6 pm", "late arrival"]):
            return (
                "**Check-In Policy & Requirements:**\n"
                "• **Guaranteed Arrival**: 24/7 check-in guaranteed.\n"
                "• **Required at Desk**: 1) Government-issued photo ID / passport, 2) Major credit/debit card for room + $50/night incidental hold, 3) Reservation confirmation.\n"
                "• **Age Requirement**: Primary guest must be 21+ years of age."
            )

        # 12. Check-in / Check-out Standard Times
        if any(w in lower for w in ["check-in", "check in", "check out", "checkout"]):
            return (
                "**Standard Timings:**\n"
                "• **Check-In**: 3:00 PM\n"
                "• **Check-Out**: 12:00 PM (Noon)\n"
                "• **Early Check-In**: Subject to room readiness; complimentary from 1:00 PM, or $30 for pre-1:00 PM guaranteed.\n"
                "• **Late Check-Out**: Complimentary until 1:00 PM based on daily occupancy; 50% day rate until 4:00 PM; full rate after 4:00 PM."
            )

        # 13. Pool / Spa / Fitness Center
        if any(w in lower for w in ["pool", "swim", "swimming", "jacuzzi", "spa", "sauna", "fitness", "gym"]):
            return (
                "**Wellness Facilities:**\n"
                "• **5th Floor Infinity Pool & Jacuzzi**: 6:00 AM – 10:00 PM daily (Keycard access).\n"
                "• **Spa & Sauna (Level 3)**: 9:00 AM – 8:00 PM (Advance booking recommended).\n"
                "• **Fitness Center (Level 3)**: 24/7 access with guest keycard."
            )

        # 14. Parking & EV Charging
        if any(w in lower for w in ["electric vehicle", "charging", "charger", "tesla", "valet", "parking"]) or re.search(r"\bev\b", lower):
            return (
                "**Parking & EV Policy:**\n"
                "• Valet Overnight: $45/night with unlimited in-and-out privileges.\n"
                "• Self-parking: $30/night in adjacent secure garage.\n"
                "• EV Charging: 8 Level-2 chargers + 2 Tesla Superchargers (Complimentary for hotel guests)."
            )

        # 15. Pet Policy
        if any(w in lower for w in ["pet", "dog", "cat", "animal"]):
            return (
                "**Pet Policy:**\n"
                "• Dogs and cats up to 50 lbs permitted (maximum 2 pets per room).\n"
                "• Pet fee: $75 non-refundable cleaning fee per stay (service animals exempt).\n"
                "• Welcome pet amenity pack provided at check-in."
            )

        # 16. WiFi Details
        if any(w in lower for w in ["wifi", "internet", "password"]):
            return (
                "**Guest Wi-Fi Details:**\n"
                "• Network: `HotelGuest` | Password: `Welcome2024` (or Room Number + Last Name login portal).\n"
                "• Front desk / Staff network: `HotelStaff_Secure` (WPA3 Enterprise)."
            )

        # 17. Airport / Transportation
        if any(w in lower for w in ["airport", "shuttle", "transfer", "limo", "limousine", "taxi", "cab"]):
            return (
                "**Transport Pricing & Procedure:**\n"
                "• Airport Sedan Transfer: $65 fixed rate each way.\n"
                "• Airport SUV Transfer: $95 fixed rate each way.\n"
                "• Standard city taxis can be hailed curbside at main entrance in ~5 minutes."
            )

        # 18. Duty Manager Escalation / Complaints
        if any(w in lower for w in ["complaint", "unhappy", "dissatisfied", "disappointed", "terrible", "bad", "manager", "escalate"]):
            return (
                "Guest complaint record created. The Duty Manager and Guest Relations team have been alerted for follow-up."
            )

        return (
            "I could not find verified hotel policy information on this in the knowledge base. Please check the property management system (PMS) or consult the Duty Manager."
        )

    @property
    def _llm_type(self) -> str:
        return "mock"


# ─── Provider Factory ─────────────────────────────────────────────────────────

def get_llm() -> BaseChatModel:
    """Return configured LLM based on LLM_PROVIDER env variable."""
    settings = get_settings()
    provider = settings.llm_provider

    logger.info("llm_provider_init", provider=provider.value)

    if provider == LLMProvider.GEMINI:
        return _get_gemini_llm(settings)
    elif provider == LLMProvider.BEDROCK:
        return _get_bedrock_llm(settings)
    else:
        logger.warning("Using mock LLM — set LLM_PROVIDER=gemini or bedrock for production")
        return MockChatModel()


def _get_gemini_llm(settings: Any) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set. Falling back to mock LLM.")

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
        )
    except Exception as e:
        logger.error("gemini_init_failed", error=str(e))
        logger.warning("Falling back to mock LLM")
        return MockChatModel()


def _get_bedrock_llm(settings: Any) -> BaseChatModel:
    try:
        import boto3
        from langchain_aws import ChatBedrockConverse

        if not settings.aws_access_key_id:
            raise ValueError("AWS_ACCESS_KEY_ID is not set. Falling back to mock LLM.")

        boto_session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
        )

        return ChatBedrockConverse(
            model=settings.bedrock_model_id,
            client=boto_session.client("bedrock-runtime"),
            temperature=0.3,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error("bedrock_init_failed", error=str(e))
        logger.warning("Falling back to mock LLM")
        return MockChatModel()

