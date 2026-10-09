import type { ConversationSummary } from '../types';

interface SidebarProps {
  conversations: ConversationSummary[];
  currentView?: 'chat' | 'upload';
  onViewChange?: (view: 'chat' | 'upload') => void;
  onNewChat?: () => void;
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar({
  conversations,
  currentView = 'chat',
  onViewChange,
  onNewChat,
}: SidebarProps) {
  return (
    <aside className="w-64 flex-shrink-0 hotel-gradient flex flex-col h-full shadow-xl">
      {/* ── Branding ── */}
      <div className="px-5 pt-6 pb-4 border-b border-white/10">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-hotel-gold/20 border border-hotel-gold/40 flex items-center justify-center">
            <span className="text-hotel-gold text-xl">✦</span>
          </div>
          <div>
            <h1 className="font-serif text-white font-semibold leading-tight text-base">
              Front Office<br />AI Copilot
            </h1>
          </div>
        </div>
        <p className="text-[10px] text-white/50 font-medium uppercase tracking-widest mt-2">
          Reception & Operations
        </p>
      </div>

      {/* ── Main Navigation ── */}
      {onViewChange && (
        <div className="px-3 py-3 border-b border-white/10 space-y-1">
          <button
            onClick={() => onViewChange('chat')}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
              currentView === 'chat'
                ? 'bg-white/20 text-white shadow-sm border border-hotel-gold/30'
                : 'text-white/70 hover:text-white hover:bg-white/10'
            }`}
          >
            <span className="text-sm">💬</span>
            <span>Front Desk Chat</span>
          </button>

          <button
            onClick={() => onViewChange('upload')}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
              currentView === 'upload'
                ? 'bg-white/20 text-white shadow-sm border border-hotel-gold/30'
                : 'text-white/70 hover:text-white hover:bg-white/10'
            }`}
          >
            <span className="text-sm">📂</span>
            <span>Upload Documents</span>
          </button>
        </div>
      )}

      {/* ── Action Button ── */}
      {onNewChat && currentView === 'chat' && (
        <div className="px-3 py-3 border-b border-white/10">
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-white/10 hover:bg-white/15 active:bg-white/20 text-white rounded-xl text-xs font-medium transition-all shadow-sm border border-white/10"
          >
            <span className="text-hotel-gold text-sm">+</span>
            <span>New Conversation</span>
          </button>
        </div>
      )}

      {/* ── Conversation History ── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
        {conversations.length > 0 ? (
          <>
            <p className="text-[10px] text-white/40 font-semibold uppercase tracking-widest px-2 mb-2">
              Recent Conversations
            </p>
            <div className="space-y-1">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className="px-3 py-2 rounded-lg hover:bg-white/10 cursor-pointer transition-all group"
                >
                  <p className="text-xs text-white/80 font-medium truncate group-hover:text-white">
                    {conv.preview}
                  </p>
                  <div className="flex items-center justify-between mt-0.5">
                    <p className="text-[10px] text-white/40">
                      {conv.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    {conv.intent && conv.intent !== 'GENERAL' && (
                      <span className="text-[9px] text-hotel-gold/70 uppercase">
                        {conv.intent.split('_')[0]}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <span className="text-3xl mb-2">💬</span>
            <p className="text-xs text-white/40">Start a conversation to see your history here</p>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="px-4 py-3 border-t border-white/10">
        <p className="text-[10px] text-white/30 text-center">
          Hotel Concierge v1.0 · MVP
        </p>
      </div>
    </aside>
  );
}
