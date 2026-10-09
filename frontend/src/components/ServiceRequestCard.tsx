import type { RequestStatus } from '../types';

interface RequestCardProps {
  id: string;
  type: string;
  roomNumber?: string;
  description: string;
  status: RequestStatus;
  priority?: string;
  createdAt: string;
  onStatusChange?: (id: string, status: string, type: string) => void;
}

const STATUS_STYLES: Record<RequestStatus, string> = {
  PENDING: 'bg-amber-100 text-amber-700',
  ASSIGNED: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-indigo-100 text-indigo-700',
  COMPLETED: 'bg-emerald-100 text-emerald-700',
  CANCELLED: 'bg-stone-100 text-stone-500',
};

const PRIORITY_DOT: Record<string, string> = {
  LOW: 'bg-stone-400',
  MEDIUM: 'bg-blue-400',
  HIGH: 'bg-orange-400',
  URGENT: 'bg-red-500 animate-pulse',
};

const TYPE_ICONS: Record<string, string> = {
  HOUSEKEEPING: '🛎️',
  MAINTENANCE: '🔧',
  COMPLAINT: '📋',
  ESCALATION: '👤',
  ROOM_SERVICE: '🍽️',
};

const NEXT_STATUS: Record<RequestStatus, RequestStatus | null> = {
  PENDING: 'ASSIGNED',
  ASSIGNED: 'IN_PROGRESS',
  IN_PROGRESS: 'COMPLETED',
  COMPLETED: null,
  CANCELLED: null,
};

// ─── Service Request Card ─────────────────────────────────────────────────────

export function ServiceRequestCard({
  id,
  type,
  roomNumber,
  description,
  status,
  priority = 'MEDIUM',
  createdAt,
  onStatusChange,
}: RequestCardProps) {
  const icon = TYPE_ICONS[type] || '📌';
  const statusStyle = STATUS_STYLES[status] || 'bg-stone-100 text-stone-600';
  const priorityDot = PRIORITY_DOT[priority] || 'bg-blue-400';
  const next = NEXT_STATUS[status];

  let time = '';
  try {
    if (createdAt) {
      const d = new Date(createdAt);
      if (!isNaN(d.getTime())) {
        time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
    }
  } catch {
    time = '';
  }

  return (
    <div className="request-card group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <span className="text-xl mt-0.5">{icon}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-xs font-bold text-hotel-muted uppercase tracking-wide">
                {type.replace(/_/g, ' ')}
              </span>
              {roomNumber && (
                <span className="text-xs bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded font-medium">
                  Room {roomNumber}
                </span>
              )}
            </div>
            <p className="text-sm text-hotel-dark font-medium line-clamp-2 leading-snug">
              {description}
            </p>
            <p className="text-[10px] text-hotel-muted mt-1">
              {id} · {time}
            </p>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${priorityDot}`} />
            <span className={`status-pill ${statusStyle}`}>{status}</span>
          </div>

          {next && onStatusChange && (
            <button
              onClick={() => onStatusChange(id, next, type)}
              className="text-[10px] font-semibold text-hotel-gold hover:text-hotel-dark transition-colors px-2 py-0.5 border border-hotel-gold rounded-full hover:bg-amber-50"
            >
              → {next.replace('_', ' ')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
