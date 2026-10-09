import React from 'react';
import type { ChatMessage } from '../types';
import { SourceBadge } from './SourceBadge';

interface MessageProps {
  message: ChatMessage;
  onRetry?: () => void;
}

// ─── Intent color map ─────────────────────────────────────────────────────────

const GUEST_ACTION_BADGES: Record<string, { icon: string; label: string; style: string }> = {
  CREATE_HOUSEKEEPING_REQUEST: { icon: '🛎️', label: 'Housekeeping Requested', style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  CREATE_MAINTENANCE_REQUEST: { icon: '🔧', label: 'Maintenance Scheduled', style: 'bg-blue-50 text-blue-700 border-blue-200' },
  CREATE_COMPLAINT: { icon: '📋', label: 'Concern Logged', style: 'bg-orange-50 text-orange-700 border-orange-200' },
  ESCALATE_TO_FRONT_DESK: { icon: '👤', label: 'Connected to Front Desk', style: 'bg-purple-50 text-purple-700 border-purple-200' },
  EMERGENCY_ALERT: { icon: '🚨', label: 'Emergency Alert Sent', style: 'bg-red-50 text-red-700 border-red-200' },
};

function formatContent(text?: string | null) {
  if (!text) return null;
  // Convert **bold** and basic newlines
  const lines = String(text).split('\n');
  return lines.map((line, i) => {
    const formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    return (
      <React.Fragment key={i}>
        <span dangerouslySetInnerHTML={{ __html: formatted }} />
        {i < lines.length - 1 && <br />}
      </React.Fragment>
    );
  });
}

// ─── Message Component ────────────────────────────────────────────────────────

export function Message({ message, onRetry }: MessageProps) {
  const isUser = message.role === 'user';
  const actionBadge = message.action ? GUEST_ACTION_BADGES[message.action] : null;

  const formattedTime = React.useMemo(() => {
    try {
      if (!message.timestamp) return '';
      const d = message.timestamp instanceof Date ? message.timestamp : new Date(message.timestamp);
      return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  }, [message.timestamp]);

  if (isUser) {
    return (
      <div className="flex justify-end animate-slide-up">
        <div className="chat-message-user">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-3 animate-slide-up">
      {/* Concierge Avatar */}
      <div className="w-8 h-8 rounded-full flex-shrink-0 hotel-gradient flex items-center justify-center shadow-md">
        <span className="text-xs text-hotel-gold">✦</span>
      </div>

      <div className="chat-message-assistant flex-1 min-w-0">
        {/* Service Action Confirmation Badge (only for real guest requests) */}
        {actionBadge && (
          <div className="mb-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${actionBadge.style}`}>
              <span>{actionBadge.icon}</span>
              {actionBadge.label}
            </span>
          </div>
        )}

        {/* Request ID highlight */}
        {message.requestId && (
          <div className="mb-2 px-2.5 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg inline-flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-emerald-700">
              Request ID: {String(message.requestId)}
            </span>
          </div>
        )}

        {/* Message content */}
        <div className="chat-content text-sm leading-relaxed text-hotel-dark">
          {formatContent(message.content)}
        </div>

        {/* Error indicator */}
        {message.error && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-red-500">⚠ Connection issue</span>
            {onRetry && (
              <button
                onClick={onRetry}
                className="text-xs text-hotel-gold hover:underline font-medium"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* RAG Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourceBadge sources={message.sources} />
        )}

        {/* Timestamp */}
        {formattedTime && (
          <p className="text-[10px] text-hotel-muted mt-1.5">
            {formattedTime}
          </p>
        )}
      </div>
    </div>
  );
}
