// ─── API Client ───────────────────────────────────────────────────────────────

const BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id?: string;
  room_number?: string;
  conversation_id?: string;
  guest_context?: Record<string, any>;
}

export interface ChatResponse {
  message: string;
  response?: string;
  session_id?: string;
  conversation_id: string;
  intent?: string;
  sub_intent?: string;
  action?: string;
  request_id?: string | null;
  sources?: Array<{ category: string; question: string; score: number; source: string; document?: string }>;
  guest_context?: { room_number?: string; guest_name?: string; [key: string]: any };
  error?: string | null;
}

export function sendMessage(body: ChatRequest): Promise<ChatResponse> {
  const payload: any = {
    message: body.message,
    session_id: body.session_id,
    conversation_id: body.conversation_id,
  };

  if (body.guest_context) {
    payload.guest_context = body.guest_context;
  } else if (body.room_number) {
    payload.guest_context = { room_number: body.room_number };
  }

  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  service_requests: { total: number; items: any[] };
  maintenance: { total: number; items: any[] };
  complaints: { total: number; items: any[] };
  escalations: { total: number; items: any[] };
}

export function getDashboardStats(): Promise<DashboardStats> {
  return request<DashboardStats>('/api/dashboard/stats');
}

// ─── Status update ────────────────────────────────────────────────────────────

export function updateServiceRequestStatus(id: string, status: string): Promise<any> {
  return request(`/api/service-requests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function updateMaintenanceStatus(id: string, status: string): Promise<any> {
  return request(`/api/maintenance/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function updateComplaintStatus(id: string, status: string): Promise<any> {
  return request(`/api/complaints/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

// ─── Health ───────────────────────────────────────────────────────────────────

export function getHealth(): Promise<any> {
  return request('/api/health');
}

// ─── Hotel Knowledge & External API ──────────────────────────────────────────

export interface HotelKnowledgeStatus {
  hotel_name: string;
  hotel_website?: string;
  api_endpoint: string;
  provider_mode: string;
  sync_enabled: boolean;
  last_synced_at: string | null;
  last_sync_count: number;
  last_sync_status: string;
  total_knowledge_documents: number;
  last_error: string | null;
  faq_documents?: {
    total_pdfs: number;
    total_qa_pairs: number;
    collection_count: number;
    last_ingested_at: string | null;
    status: string;
    categories: string[];
    total_categories: number;
  };
}

export function getHotelKnowledgeStatus(): Promise<HotelKnowledgeStatus> {
  return request<HotelKnowledgeStatus>('/api/hotel-knowledge/status');
}

export function syncHotelKnowledge(): Promise<{
  status: string;
  synced_count: number;
  hotel_name: string;
  synced_at: string;
}> {
  return request('/api/hotel-knowledge/sync', {
    method: 'POST',
  });
}

export function ingestFaqDocuments(): Promise<{
  success: boolean;
  total_pdfs: number;
  total_qa_pairs: number;
  categories_count: number;
  ingested_at: string;
}> {
  return request('/api/hotel-knowledge/ingest-documents', {
    method: 'POST',
  });
}

export interface FaqDocumentItem {
  filename: string;
  path: string;
  size_bytes: number;
  formatted_size: string;
  modified_at: string;
  qa_count: number;
  category: string;
  last_indexed?: string | null;
}

export interface FaqDocumentsListResponse {
  documents: FaqDocumentItem[];
  total_documents: number;
  total_qa_count: number;
  collection_count: number;
}

export function listFaqDocuments(): Promise<FaqDocumentsListResponse> {
  return request<FaqDocumentsListResponse>('/api/hotel-knowledge/documents');
}

export async function uploadFaqDocuments(files: File[]): Promise<{
  success: boolean;
  uploaded_files: string[];
  total_uploaded: number;
  ingest_result: any;
  document_stats: any;
  error?: string;
}> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const res = await fetch(`${BASE_URL}/api/hotel-knowledge/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }
  return res.json();
}

export function deleteFaqDocument(filename: string): Promise<{
  success: boolean;
  deleted_file: string;
  document_stats: any;
}> {
  return request(`/api/hotel-knowledge/documents/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
}

export function clearAllFaqDocuments(): Promise<{
  success: boolean;
  message: string;
  document_stats: any;
}> {
  return request('/api/hotel-knowledge/clear-all', {
    method: 'POST',
  });
}

// ─── LangSmith Observability ──────────────────────────────────────────────────

export interface LangsmithStatus {
  enabled: boolean;
  connected: boolean;
  project: string;
  endpoint: string;
  has_api_key: boolean;
  api_key_masked: string | null;
  error: string | null;
}

export function getLangsmithStatus(): Promise<LangsmithStatus> {
  return request<LangsmithStatus>('/api/observability/langsmith');
}

