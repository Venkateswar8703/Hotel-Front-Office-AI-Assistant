import { useEffect, useState } from 'react';
import { useServiceRequests } from '../hooks/useServiceRequests';
import { ServiceRequestCard } from './ServiceRequestCard';
import { getHealth, getHotelKnowledgeStatus, syncHotelKnowledge, ingestFaqDocuments, HotelKnowledgeStatus } from '../api/client';

// ─── Staff Dashboard ──────────────────────────────────────────────────────────

export function StaffDashboard() {
  const { stats, loading, error, refresh, updateStatus } = useServiceRequests(8000);
  const [health, setHealth] = useState<any>(null);
  const [knowledge, setKnowledge] = useState<HotelKnowledgeStatus | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isIngestingDocs, setIsIngestingDocs] = useState(false);
  const [syncSuccessMsg, setSyncSuccessMsg] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<'all' | 'housekeeping' | 'maintenance' | 'complaints' | 'escalations'>('all');

  const fetchKnowledge = () => {
    getHotelKnowledgeStatus().then(setKnowledge).catch(() => {});
  };

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
    fetchKnowledge();
  }, []);

  const handleSyncKnowledge = async () => {
    setIsSyncing(true);
    setSyncSuccessMsg(null);
    try {
      const res = await syncHotelKnowledge();
      setSyncSuccessMsg(`Synced ${res.synced_count} FAQs successfully!`);
      fetchKnowledge();
      getHealth().then(setHealth).catch(() => {});
      setTimeout(() => setSyncSuccessMsg(null), 4000);
    } catch {
      setSyncSuccessMsg('Sync failed. Please check backend connection.');
      setTimeout(() => setSyncSuccessMsg(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleIngestDocuments = async () => {
    setIsIngestingDocs(true);
    setSyncSuccessMsg(null);
    try {
      const res = await ingestFaqDocuments();
      setSyncSuccessMsg(`Indexed ${res.total_qa_pairs} Q&As across ${res.total_pdfs} PDF documents!`);
      fetchKnowledge();
      getHealth().then(setHealth).catch(() => {});
      setTimeout(() => setSyncSuccessMsg(null), 5000);
    } catch {
      setSyncSuccessMsg('Document ingestion failed.');
      setTimeout(() => setSyncSuccessMsg(null), 4000);
    } finally {
      setIsIngestingDocs(false);
    }
  };

  const pendingCount = (items: any[]) =>
    items.filter((i) => i.status === 'PENDING' || i.status === 'ASSIGNED').length;

  const allRequests = stats
    ? [
        ...stats.service_requests.items.map((r) => ({ ...r, _type: 'HOUSEKEEPING' })),
        ...stats.maintenance.items.map((r) => ({ ...r, _type: 'MAINTENANCE' })),
        ...stats.complaints.items.map((r) => ({ ...r, _type: 'COMPLAINT' })),
        ...stats.escalations.items.map((r) => ({ ...r, _type: 'ESCALATION' })),
      ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    : [];

  const filteredRequests = activeCategory === 'all'
    ? allRequests
    : allRequests.filter((r) => {
        if (activeCategory === 'housekeeping') return r._type === 'HOUSEKEEPING';
        if (activeCategory === 'maintenance') return r._type === 'MAINTENANCE';
        if (activeCategory === 'complaints') return r._type === 'COMPLAINT';
        if (activeCategory === 'escalations') return r._type === 'ESCALATION';
        return true;
      });

  return (
    <div className="flex flex-col h-full w-full bg-hotel-cream min-w-0">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-stone-100 shadow-sm">
        <div>
          <h2 className="font-serif font-semibold text-hotel-dark text-lg">Staff Operations Dashboard</h2>
          <p className="text-xs text-hotel-muted">Real-time service request management</p>
        </div>
        <div className="flex items-center gap-3">
          {health && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-full">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-[11px] text-emerald-700 font-medium">
                {health.document_count} FAQs indexed
              </span>
            </div>
          )}
          {health?.langsmith && (
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium ${
                health.langsmith.connected
                  ? 'bg-purple-50 border-purple-200 text-purple-700'
                  : health.langsmith.enabled
                  ? 'bg-amber-50 border-amber-200 text-amber-700'
                  : 'bg-stone-50 border-stone-200 text-stone-500'
              }`}
              title={`LangSmith: ${health.langsmith.enabled ? 'Tracing Active' : 'Off (Set LANGSMITH_API_KEY in .env)'}\nProject: ${health.langsmith.project}`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  health.langsmith.connected
                    ? 'bg-purple-500 animate-pulse'
                    : health.langsmith.enabled
                    ? 'bg-amber-400'
                    : 'bg-stone-300'
                }`}
              />
              <span>
                LangSmith: {health.langsmith.connected ? 'Connected' : health.langsmith.enabled ? 'Active' : 'Off'}
              </span>
            </div>
          )}
          <button
            onClick={refresh}
            className="p-2 text-hotel-muted hover:text-hotel-dark hover:bg-stone-100 rounded-lg transition-all"
            title="Refresh"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Hotel Knowledge & Document RAG Status ── */}
      {knowledge && (
        <div className="mx-6 mt-4 grid grid-cols-1 lg:grid-cols-2 gap-3">
          {/* Card 1: External Hotel Knowledge API */}
          <div className="p-4 bg-white border border-stone-200 rounded-2xl shadow-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-xl text-amber-700 flex-shrink-0">
                🏨
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm text-hotel-dark truncate">{knowledge.hotel_name}</h3>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-emerald-100 text-emerald-700 flex-shrink-0">
                    {knowledge.provider_mode === 'remote_rest' ? 'Live API' : 'Active Knowledge'}
                  </span>
                </div>
                <p className="text-xs text-hotel-muted mt-0.5 truncate">
                  {knowledge.total_knowledge_documents} hotel FAQs indexed · {knowledge.api_endpoint}
                  {knowledge.last_synced_at && ` · Synced: ${new Date(knowledge.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                </p>
              </div>
            </div>

            <button
              onClick={handleSyncKnowledge}
              disabled={isSyncing}
              className="px-3 py-1.5 rounded-xl hotel-gradient text-white text-xs font-semibold hover:opacity-90 active:scale-95 transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-50 flex-shrink-0"
              title="Sync latest FAQs from Hotel Knowledge API"
            >
              <span className={isSyncing ? 'animate-spin' : ''}>↻</span>
              {isSyncing ? 'Syncing...' : 'Sync API FAQs'}
            </button>
          </div>

          {/* Card 2: 24 PDF FAQ Documents RAG */}
          <div className="p-4 bg-white border border-stone-200 rounded-2xl shadow-sm flex items-center justify-between gap-3">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-xl text-blue-700 flex-shrink-0">
                📚
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm text-hotel-dark truncate">FAQ Folder Documents</h3>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-blue-100 text-blue-700 flex-shrink-0">
                    {knowledge.faq_documents ? `${knowledge.faq_documents.total_pdfs} PDFs` : '24 PDFs'}
                  </span>
                </div>
                <p className="text-xs text-hotel-muted mt-0.5 truncate">
                  {knowledge.faq_documents
                    ? `${knowledge.faq_documents.total_qa_pairs.toLocaleString()} Q&As across ${knowledge.faq_documents.total_categories} categories`
                    : '3,405 Q&As indexed into ChromaDB'}
                  {knowledge.faq_documents?.last_ingested_at &&
                    ` · Indexed: ${new Date(knowledge.faq_documents.last_ingested_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                </p>
              </div>
            </div>

            <button
              onClick={handleIngestDocuments}
              disabled={isIngestingDocs}
              className="px-3 py-1.5 rounded-xl bg-hotel-charcoal text-white text-xs font-semibold hover:bg-black active:scale-95 transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-50 flex-shrink-0"
              title="Reload and refresh all hotel documents for the AI assistant"
            >
              <span className={isIngestingDocs ? 'animate-spin' : ''}>↻</span>
              <span>{isIngestingDocs ? 'Refreshing...' : 'Refresh Knowledge'}</span>
            </button>
          </div>
        </div>
      )}

      {syncSuccessMsg && (
        <div className="mx-6 mt-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 font-medium flex items-center gap-2 animate-fade-in">
          <span>✓</span>
          <span>{syncSuccessMsg}</span>
        </div>
      )}

      {/* ── KPI Cards ── */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 px-6 py-4">
          {[
            { label: 'Service Requests', count: stats.service_requests.total, pending: pendingCount(stats.service_requests.items), icon: '🛎️', color: 'border-blue-200 bg-blue-50' },
            { label: 'Maintenance', count: stats.maintenance.total, pending: pendingCount(stats.maintenance.items), icon: '🔧', color: 'border-orange-200 bg-orange-50' },
            { label: 'Complaints', count: stats.complaints.total, pending: pendingCount(stats.complaints.items), icon: '📋', color: 'border-red-200 bg-red-50' },
            { label: 'Escalations', count: stats.escalations.total, pending: pendingCount(stats.escalations.items), icon: '👤', color: 'border-purple-200 bg-purple-50' },
          ].map((kpi) => (
            <div key={kpi.label} className={`rounded-xl border p-4 ${kpi.color} transition-all hover:shadow-sm`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold text-hotel-muted uppercase tracking-wide">{kpi.label}</p>
                  <p className="text-3xl font-bold text-hotel-dark mt-1">{kpi.count}</p>
                </div>
                <span className="text-2xl">{kpi.icon}</span>
              </div>
              {kpi.pending > 0 && (
                <div className="mt-2 flex items-center gap-1">
                  <span className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
                  <span className="text-xs text-amber-700 font-medium">{kpi.pending} pending</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Category Filter ── */}
      <div className="px-6 pb-3 flex gap-2">
        {(['all', 'housekeeping', 'maintenance', 'complaints', 'escalations'] as const).map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold capitalize transition-all ${
              activeCategory === cat
                ? 'bg-hotel-charcoal text-white shadow-sm'
                : 'bg-white border border-stone-200 text-hotel-muted hover:border-hotel-gold hover:text-hotel-dark'
            }`}
          >
            {cat === 'all' ? '📌 All' : cat}
          </button>
        ))}
      </div>

      {/* ── Requests List ── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-6 pb-6">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-center">
              <span className="text-3xl animate-spin inline-block">⟳</span>
              <p className="text-sm text-hotel-muted mt-2">Loading requests...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-center">
              <span className="text-3xl">⚠️</span>
              <p className="text-sm text-red-500 mt-2">Failed to load. Is the backend running?</p>
              <button onClick={refresh} className="text-xs text-hotel-gold mt-2 hover:underline">Retry</button>
            </div>
          </div>
        ) : filteredRequests.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-center">
              <span className="text-4xl">✅</span>
              <p className="text-sm text-hotel-muted mt-2 font-medium">All clear — no requests</p>
              <p className="text-xs text-hotel-muted mt-1">New guest requests will appear here</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredRequests.map((req: any) => (
              <ServiceRequestCard
                key={req.request_id || req.ticket_id || req.complaint_id || req.escalation_id}
                id={req.request_id || req.ticket_id || req.complaint_id || req.escalation_id}
                type={req._type}
                roomNumber={req.room_number}
                description={req.description || req.reason || req.issue_type}
                status={req.status}
                priority={req.priority}
                createdAt={req.created_at}
                onStatusChange={updateStatus}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
