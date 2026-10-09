import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Message } from './Message';
import { TypingIndicator } from './TypingIndicator';
import { SuggestedPrompts } from './SuggestedPrompts';
import { getHotelKnowledgeStatus, HotelKnowledgeStatus } from '../api/client';
import type { ChatMessage } from '../types';

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (msg: string) => void;
  onClear: () => void;
  onOpenUpload?: () => void;
}

// ─── Chat Panel ───────────────────────────────────────────────────────────────

export function ChatPanel({
  messages,
  isLoading,
  onSendMessage,
  onClear,
  onOpenUpload,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [knowledge, setKnowledge] = useState<HotelKnowledgeStatus | null>(null);
  const [statusNotification, setStatusNotification] = useState<{
    type: 'success' | 'error' | 'info';
    text: string;
  } | null>(null);
  const [showStatsModal, setShowStatsModal] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const hasMessages = messages.length > 1; // more than welcome message

  // Fetch knowledge status on mount
  const fetchKnowledge = useCallback(async () => {
    try {
      const data = await getHotelKnowledgeStatus();
      setKnowledge(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchKnowledge();
  }, [fetchKnowledge]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    onSendMessage(text);
  }, [input, isLoading, onSendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const totalDocs = knowledge?.total_knowledge_documents ?? knowledge?.faq_documents?.collection_count ?? 0;
  const totalPdfs = knowledge?.faq_documents?.total_pdfs ?? 0;

  return (
    <div className="flex flex-col h-full w-full bg-hotel-cream min-w-0 relative">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 sm:px-8 py-3.5 bg-white border-b border-stone-100 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl hotel-gradient flex items-center justify-center shadow-md">
            <span className="text-hotel-gold text-lg">✦</span>
          </div>
          <div>
            <h2 className="font-serif font-semibold text-hotel-dark text-lg leading-tight">
              Front Office AI Copilot
            </h2>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <p className="text-xs text-hotel-muted">Reception & Front Desk Operations</p>
            </div>
          </div>
        </div>

        {/* ── Top Bar Controls: Upload & Clear ── */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Upload & Knowledge Action Control */}
          <div className="flex items-center gap-1.5 bg-stone-100 border border-stone-300/80 rounded-xl p-1 shadow-sm">
            <button
              onClick={() => (onOpenUpload ? onOpenUpload() : setShowStatsModal(!showStatsModal))}
              title="Click to view Knowledge Base details or upload documents"
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-stone-700 hover:text-stone-900 hover:bg-white rounded-lg transition-all"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-stone-800">{totalDocs.toLocaleString()} Docs</span>
              <span className="text-[11px] font-medium text-stone-500">({totalPdfs} PDFs)</span>
            </button>

            <button
              onClick={onOpenUpload ? onOpenUpload : () => setShowStatsModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-sm bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white border border-amber-700 active:scale-95 shadow-amber-600/20"
              title="Upload FAQ documents to ChromaDB knowledge base"
            >
              <svg
                className="w-3.5 h-3.5 text-amber-100"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.4}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                />
              </svg>
              <span>Upload Documents</span>
            </button>
          </div>

          {/* Clear conversation button */}
          {hasMessages && (
            <button
              onClick={onClear}
              className="p-2 text-stone-500 hover:text-stone-900 hover:bg-stone-100 rounded-xl border border-stone-200 transition-all shadow-sm"
              title="Clear conversation"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* ── Knowledge Base Popover Details Modal ── */}
      {showStatsModal && (
        <div className="absolute top-16 right-8 z-30 bg-white rounded-2xl shadow-2xl border border-stone-200 p-4 w-80 text-left animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-stone-100">
            <h3 className="font-bold text-sm text-stone-900 flex items-center gap-1.5">
              <span>📚</span> Hotel Knowledge Base
            </h3>
            <button
              onClick={() => setShowStatsModal(false)}
              className="text-stone-400 hover:text-stone-700 text-xs px-1 font-bold"
            >
              ✕
            </button>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-stone-100">
              <span className="text-stone-600">Total Indexed Items:</span>
              <span className="font-bold text-stone-900">{totalDocs.toLocaleString()}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-stone-100">
              <span className="text-stone-600">PDF FAQ Documents:</span>
              <span className="font-bold text-stone-900">{totalPdfs} files</span>
            </div>
            <div className="flex justify-between py-1 border-b border-stone-100">
              <span className="text-stone-600">Extracted Q&A Pairs:</span>
              <span className="font-bold text-stone-900">
                {knowledge?.faq_documents?.total_qa_pairs?.toLocaleString() || '3,552'} pairs
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-stone-600">Vector Engine:</span>
              <span className="font-bold text-emerald-700">ChromaDB + MiniLM</span>
            </div>
          </div>
          <button
            onClick={() => {
              setShowStatsModal(false);
              if (onOpenUpload) onOpenUpload();
            }}
            className="w-full mt-3 py-2 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-md border border-amber-700"
          >
            <span>📂 Open Document Upload & Knowledge Manager</span>
          </button>
        </div>
      )}

      {/* ── Status Notification Toast ── */}
      {statusNotification && (
        <div
          className={`mx-6 sm:mx-8 mt-3 px-4 py-2.5 rounded-xl border text-xs font-medium flex items-center justify-between shadow-sm transition-all animate-in fade-in duration-200 ${
            statusNotification.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : statusNotification.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-amber-50 border-amber-200 text-amber-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {statusNotification.type === 'info' && (
              <span className="w-3.5 h-3.5 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
            )}
            <span>{statusNotification.text}</span>
          </div>
          <button
            onClick={() => setStatusNotification(null)}
            className="text-stone-400 hover:text-stone-700 ml-3"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Messages Container ── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 sm:px-8 py-6">
        <div className="max-w-4xl mx-auto w-full space-y-4">
          {messages.map((msg) =>
            msg.isLoading ? (
              <TypingIndicator key={msg.id} />
            ) : (
              <Message key={msg.id} message={msg} />
            )
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ── Suggested Prompts (only when first-load) ── */}
      {!hasMessages && (
        <div className="w-full flex-shrink-0">
          <div className="max-w-4xl mx-auto w-full">
            <SuggestedPrompts onSelect={onSendMessage} disabled={isLoading} />
          </div>
        </div>
      )}

      {/* ── Input Bar ── */}
      <div className="w-full flex-shrink-0 px-4 sm:px-8 pb-5 pt-2.5 bg-white/95 backdrop-blur border-t border-stone-100">
        <div className="max-w-4xl mx-auto w-full">
          <div className="flex items-end gap-2 bg-stone-50 border border-stone-200 rounded-2xl px-4 py-2.5 focus-within:border-hotel-gold focus-within:ring-2 focus-within:ring-hotel-gold/20 transition-all shadow-sm">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Query hotel policies, look up procedures, or dispatch requests (e.g. 'Dispatch towels to 405')…"
              disabled={isLoading}
              rows={1}
              className="flex-1 bg-transparent text-sm text-hotel-dark placeholder-hotel-muted resize-none outline-none leading-relaxed max-h-32 py-1 disabled:opacity-60"
              style={{ minHeight: '26px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="w-9 h-9 rounded-xl hotel-gradient flex items-center justify-center flex-shrink-0 disabled:opacity-40 hover:opacity-90 transition-all active:scale-95 shadow-md"
            >
              <svg className="w-4 h-4 text-hotel-gold" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>
          <p className="text-[11px] text-hotel-muted text-center mt-2 font-medium">
            Front Office AI Copilot · Powered by RAG + LangGraph
          </p>
        </div>
      </div>
    </div>
  );
}
