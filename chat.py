#!/usr/bin/env python3
"""
Hotel AI Concierge — Interactive Terminal CLI

Allows interacting with the Hotel Concierge chatbot and RAG knowledge base
directly from the terminal.

Usage:
    # Interactive chat session:
    python chat.py

    # With specific room number:
    python chat.py --room 402

    # Single-shot query:
    python chat.py "What are the breakfast timings?"
    python chat.py "Can I get extra towels?" --room 305
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any

# Color helpers
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Palette
    GOLD = "\033[38;5;214m"
    AMBER = "\033[38;5;208m"
    BLUE = "\033[38;5;75m"
    CYAN = "\033[38;5;80m"
    GREEN = "\033[38;5;78m"
    RED = "\033[38;5;203m"
    GRAY = "\033[38;5;244m"
    WHITE = "\033[38;5;255m"
    PURPLE = "\033[38;5;141m"

def c(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

API_URL = os.environ.get("CONCIERGE_API_URL", "http://localhost:8000")


def check_api_server(base_url: str) -> bool:
    """Check if the backend server is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url}/api/health", headers={"User-Agent": "ConciergeCLI/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_chat_http(
    message: str,
    base_url: str,
    room_number: str = "204",
    session_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Send chat message to backend FastAPI server."""
    import urllib.request
    
    payload = {
        "message": message,
        "session_id": session_id or f"cli-session-{room_number}",
        "conversation_id": conversation_id,
        "guest_context": {"room_number": room_number},
    }
    
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ConciergeCLI/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_status_http(base_url: str) -> dict[str, Any] | None:
    """Fetch hotel knowledge and RAG documents status."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{base_url}/api/hotel-knowledge/status", headers={"User-Agent": "ConciergeCLI/1.0"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def trigger_sync_http(base_url: str) -> dict[str, Any] | None:
    """Trigger external hotel knowledge sync."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{base_url}/api/hotel-knowledge/sync", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def trigger_reindex_http(base_url: str) -> dict[str, Any] | None:
    """Trigger PDF FAQ folder re-indexing."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{base_url}/api/hotel-knowledge/ingest-documents", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=90.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def print_banner(status: dict[str, Any] | None, room_number: str):
    """Print terminal header banner."""
    hotel_name = status.get("hotel_name", "Grand Horizon Hotel & Suites") if status else "Grand Horizon Hotel & Suites"
    faq_docs = status.get("faq_documents", {}) if status else {}
    pdf_count = faq_docs.get("total_pdfs", 24)
    qa_count = faq_docs.get("total_qa_pairs", 3405)

    print()
    print(c("╔═══════════════════════════════════════════════════════════════════╗", Colors.GOLD))
    print(c(f"║   🏨  {hotel_name.center(56)}  ║", Colors.GOLD))
    print(c("║   AI Concierge & Knowledge RAG — Terminal Interface               ║", Colors.GOLD))
    print(c("╚═══════════════════════════════════════════════════════════════════╝", Colors.GOLD))
    print(
        f"  {c('● Room:', Colors.GRAY)} {c(room_number, Colors.CYAN + Colors.BOLD)}  "
        f"  {c('● Knowledge Base:', Colors.GRAY)} {c(f'{qa_count:,} Q&As from {pdf_count} PDFs', Colors.GREEN)}  "
        f"  {c('● Mode:', Colors.GRAY)} {c('Live RAG', Colors.AMBER)}"
    )
    print(c("  Commands: /room <number>, /status, /sync, /reindex, /help, /exit", Colors.GRAY))
    print(c("─" * 69, Colors.DIM))
    print()


def render_response(res: dict[str, Any]):
    """Pretty-print the concierge AI response with RAG citations."""
    message = res.get("message") or res.get("response", "No response.")
    intent = res.get("intent", "")
    request_id = res.get("request_id")
    sources = res.get("sources", [])

    # Concierge Response
    print()
    print(f"{c('🛎️  Concierge:', Colors.GOLD + Colors.BOLD)}")
    print(f"   {message}")

    # Service Request / Ticket Created
    if request_id:
        print(f"   {c('✓ Ticket Created:', Colors.GREEN + Colors.BOLD)} {c(request_id, Colors.WHITE)} ({intent})")

    # Sources & Citations
    if sources and isinstance(sources, list) and len(sources) > 0:
        print()
        print(f"   {c('📚 Verified Sources:', Colors.GRAY)}")
        for src in sources[:3]:
            score = round(src.get("score", 0) * 100)
            doc = src.get("document") or src.get("category") or "FAQ"
            question = src.get("question", "")
            q_snippet = f" · \"{question[:45]}...\"" if len(question) > 45 else (f" · \"{question}\"" if question else "")
            print(f"      {c('•', Colors.AMBER)} {c(doc, Colors.WHITE)} {c(f'[{score}% match]', Colors.GREEN)}{c(q_snippet, Colors.GRAY)}")

    print()


def interactive_chat(base_url: str, initial_room: str = "204"):
    """Run interactive REPL terminal chat session."""
    room_number = initial_room
    conversation_id = str(uuid.uuid4())
    session_id = f"cli-session-{room_number}"

    is_live = check_api_server(base_url)
    if not is_live:
        print(c(f"⚠️  Backend server not detected at {base_url}.", Colors.RED))
        print(c("Please ensure backend is running or run: uvicorn app.main:app --port 8000", Colors.GRAY))
        print()

    status = get_status_http(base_url) if is_live else None
    print_banner(status, room_number)

    while True:
        try:
            prompt_label = f"{c('Guest [Room ' + room_number + ']', Colors.CYAN + Colors.BOLD)}{c(' > ', Colors.WHITE)}"
            user_input = input(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            print(c("\n\nThank you for using the AI Concierge. Have a wonderful stay! 👋\n", Colors.GOLD))
            break

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in ["/exit", "/quit", "exit", "quit"]:
            print(c("\nThank you for choosing Grand Horizon Hotel & Suites. Goodbye! 👋\n", Colors.GOLD))
            break

        if lower in ["/help", "help"]:
            print(c("\nTerminal Commands:", Colors.BOLD))
            print(f"  {c('/room <number>', Colors.CYAN)}  : Switch active room number (e.g. /room 501)")
            print(f"  {c('/status', Colors.CYAN)}         : View knowledge base and RAG collection stats")
            print(f"  {c('/sync', Colors.CYAN)}           : Sync latest hotel knowledge profile")
            print(f"  {c('/reindex', Colors.CYAN)}        : Re-index all 24 PDF files in FAQ folder")
            print(f"  {c('/clear', Colors.CYAN)}          : Start a new conversation")
            print(f"  {c('/exit', Colors.CYAN)}           : Exit the terminal chat\n")
            continue

        if lower.startswith("/room"):
            parts = user_input.split()
            if len(parts) > 1 and parts[1].strip():
                room_number = parts[1].strip()
                session_id = f"cli-session-{room_number}"
                print(c(f"✓ Switched to Room {room_number}\n", Colors.GREEN))
            else:
                print(c("Usage: /room <room_number> (e.g. /room 302)\n", Colors.AMBER))
            continue

        if lower == "/clear":
            conversation_id = str(uuid.uuid4())
            print(c("✓ Started new conversation session.\n", Colors.GREEN))
            continue

        if lower == "/status":
            print(c("\nFetching system status...", Colors.GRAY))
            st = get_status_http(base_url)
            if st:
                faq_st = st.get("faq_documents", {})
                print(c(f"🏨 Hotel: {st.get('hotel_name')}", Colors.BOLD))
                print(f"   API Provider: {st.get('provider_mode')}")
                print(f"   Total Indexed Docs: {c(str(st.get('total_knowledge_documents', 0)), Colors.GREEN)}")
                print(f"   PDF Documents: {c(str(faq_st.get('total_pdfs', 0)), Colors.CYAN)} files")
                print(f"   Q&A Pairs: {c(str(faq_st.get('total_qa_pairs', 0)), Colors.CYAN)} pairs across {faq_st.get('total_categories', 0)} categories")
                print(f"   Collection Status: {c(faq_st.get('status', 'unknown'), Colors.GREEN)}\n")
            else:
                print(c("Failed to fetch status from backend.\n", Colors.RED))
            continue

        if lower == "/sync":
            print(c("Syncing Hotel Knowledge API...", Colors.GRAY))
            res = trigger_sync_http(base_url)
            if res and not res.get("error"):
                print(c(f"✓ Successfully synced {res.get('synced_count', 0)} FAQs!\n", Colors.GREEN))
            else:
                print(c(f"Sync failed: {res}\n", Colors.RED))
            continue

        if lower == "/reindex":
            print(c("Re-indexing all 24 PDF files in FAQ folder (this may take ~30 seconds)...", Colors.AMBER))
            res = trigger_reindex_http(base_url)
            if res and res.get("success"):
                print(c(f"✓ Re-indexed {res.get('total_qa_pairs')} Q&As across {res.get('total_pdfs')} PDFs!\n", Colors.GREEN))
            else:
                print(c(f"Re-indexing failed: {res}\n", Colors.RED))
            continue

        # Send Chat Message
        try:
            res = send_chat_http(
                message=user_input,
                base_url=base_url,
                room_number=room_number,
                session_id=session_id,
                conversation_id=conversation_id,
            )
            render_response(res)
        except Exception as e:
            print(c(f"\n⚠️  Error sending message: {e}\n", Colors.RED))


def single_query(query: str, base_url: str, room_number: str = "204"):
    """Run a single query and exit."""
    try:
        res = send_chat_http(message=query, base_url=base_url, room_number=room_number)
        render_response(res)
    except Exception as e:
        print(c(f"Error: {e}", Colors.RED), file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Hotel AI Concierge & Knowledge RAG — Terminal Client")
    parser.add_argument("query", nargs="*", help="Optional single-shot question to ask")
    parser.add_argument("--room", default="204", help="Guest room number (default: 204)")
    parser.add_argument("--url", default=API_URL, help=f"Backend API URL (default: {API_URL})")

    args = parser.parse_args()

    if args.query:
        single_query(" ".join(args.query), base_url=args.url, room_number=args.room)
    else:
        interactive_chat(base_url=args.url, initial_room=args.room)


if __name__ == "__main__":
    main()
