import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, GuestContext, ConversationSummary } from '../types';
import { sendMessage } from '../api/client';

// ─── useChat Hook ─────────────────────────────────────────────────────────────

function genId() {
  return Math.random().toString(36).slice(2);
}

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    '**Front Office AI Copilot** 🏨\n\nReady to assist reception and front desk operations. How can I help with your shift today?\n\n' +
    '• **Policy & Guidelines** — Check-in/out rules, late checkout pricing, deposits, and pet policies\n' +
    '• **Guest Requests & Dispatch** — Log housekeeping (HK), engineering maintenance (MT), and room service\n' +
    '• **Information Lookup** — Amenities, dining hours, EV charging, transport, and local services\n' +
    '• **Complaints & Escalations** — Log guest incident records and escalate to Duty Manager\n\n' +
    'Enter an operational query or specify a room number (e.g. *"Log maintenance for Room 405: AC leaking"*).',
  timestamp: new Date(),
};

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [isLoading, setIsLoading] = useState(false);
  const [guestContext, setGuestContext] = useState<GuestContext>({
    session_id: genId(),
  });
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const conversationIdRef = useRef<string | undefined>(undefined);

  const sendChatMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMsg: ChatMessage = {
        id: genId(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };

      const loadingId = genId();
      const loadingMsg: ChatMessage = {
        id: loadingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      };

      setMessages((prev) => [...prev, userMsg, loadingMsg]);
      setIsLoading(true);

      try {
        const res = await sendMessage({
          message: text,
          session_id: guestContext.session_id,
          room_number: guestContext.room_number,
          conversation_id: conversationIdRef.current,
        });

        conversationIdRef.current = res.conversation_id;

        if (res.guest_context?.room_number) {
          setGuestContext((prev) => ({
            ...prev,
            room_number: res.guest_context!.room_number,
            guest_name: res.guest_context!.guest_name,
            conversation_id: res.conversation_id,
          }));
        }

        const replyContent = res.message || res.response || (res as any).content || 'I have processed your request.';

        const assistantMsg: ChatMessage = {
          id: genId(),
          role: 'assistant',
          content: replyContent,
          timestamp: new Date(),
          intent: res.intent,
          action: res.action,
          requestId: res.request_id || undefined,
          sources: res.sources,
        };

        setMessages((prev) => prev.filter((m) => m.id !== loadingId).concat(assistantMsg));

        // Add to sidebar conversation history
        setConversations((prev) => [
          { id: genId(), preview: text, timestamp: new Date(), intent: res.intent },
          ...prev.slice(0, 19),
        ]);
      } catch (err) {
        console.error('Error sending chat message:', err);
        setMessages((prev) =>
          prev.filter((m) => m.id !== loadingId).concat({
            id: genId(),
            role: 'assistant',
            content: 'Sorry, I encountered a connection error. Please check that the backend is running and try again.',
            timestamp: new Date(),
            error: true,
          })
        );
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, guestContext]
  );

  const clearConversation = useCallback(() => {
    conversationIdRef.current = undefined;
    setMessages([WELCOME]);
    setGuestContext((prev) => ({ session_id: prev.session_id }));
  }, []);

  const setRoomNumber = useCallback((room: string) => {
    setGuestContext((prev) => ({ ...prev, room_number: room }));
  }, []);

  return {
    messages,
    isLoading,
    guestContext,
    conversations,
    sendChatMessage,
    clearConversation,
    setRoomNumber,
  };
}
