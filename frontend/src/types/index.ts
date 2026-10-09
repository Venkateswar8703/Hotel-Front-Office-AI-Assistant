// ─── Shared TypeScript Types ──────────────────────────────────────────────────

export type RequestStatus = 'PENDING' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export interface RagSource {
  category: string;
  question: string;
  score: number;
  source: string;
  document?: string;
}

// Alias for backward compatibility
export type RAGSource = RagSource;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  intent?: string;
  action?: string;
  requestId?: string;
  sources?: RagSource[];
  error?: boolean;
  isLoading?: boolean;
}

export interface GuestContext {
  session_id: string;
  room_number?: string;
  guest_name?: string;
  conversation_id?: string;
}

export interface ConversationSummary {
  id: string;
  preview: string;
  timestamp: Date;
  intent?: string;
}
