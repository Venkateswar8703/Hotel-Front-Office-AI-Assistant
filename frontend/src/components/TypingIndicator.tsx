
// ─── Typing Indicator ─────────────────────────────────────────────────────────

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-3 animate-fade-in">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-full flex-shrink-0 hotel-gradient flex items-center justify-center shadow-md">
        <span className="text-xs">✦</span>
      </div>

      <div className="chat-message-assistant flex items-center gap-1 px-4 py-3">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}
