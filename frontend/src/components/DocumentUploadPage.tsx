import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  listFaqDocuments,
  uploadFaqDocuments,
  deleteFaqDocument,
  clearAllFaqDocuments,
  ingestFaqDocuments,
  getHotelKnowledgeStatus,
  FaqDocumentItem,
  HotelKnowledgeStatus,
} from '../api/client';

interface DocumentUploadPageProps {
  onBackToChat: () => void;
}

export function DocumentUploadPage({ onBackToChat }: DocumentUploadPageProps) {
  const [documents, setDocuments] = useState<FaqDocumentItem[]>([]);
  const [totalDocsCount, setTotalDocsCount] = useState<number>(0);
  const [totalQaCount, setTotalQaCount] = useState<number>(0);
  const [collectionCount, setCollectionCount] = useState<number>(0);
  const [knowledgeStatus, setKnowledgeStatus] = useState<HotelKnowledgeStatus | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info';
    text: string;
  } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const showNotification = (type: 'success' | 'error' | 'info', text: string, duration = 5000) => {
    setNotification({ type, text });
    setTimeout(() => {
      setNotification((curr) => (curr?.text === text ? null : curr));
    }, duration);
  };

  const fetchKnowledgeData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [docRes, statusRes] = await Promise.all([
        listFaqDocuments(),
        getHotelKnowledgeStatus(),
      ]);

      setDocuments(docRes.documents || []);
      setTotalDocsCount(docRes.total_documents || 0);
      setTotalQaCount(docRes.total_qa_count || 0);
      setCollectionCount(docRes.collection_count || 0);
      setKnowledgeStatus(statusRes);
    } catch (err: any) {
      showNotification('error', `Failed to load document list: ${err.message || 'Network error'}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKnowledgeData();
  }, [fetchKnowledgeData]);

  // Handle Drag & Drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const pdfFiles = Array.from(e.dataTransfer.files).filter((file) =>
        file.name.toLowerCase().endsWith('.pdf')
      );
      if (pdfFiles.length === 0) {
        showNotification('error', 'Please drop PDF files only.');
        return;
      }
      setSelectedFiles((prev) => [...prev, ...pdfFiles]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const pdfFiles = Array.from(e.target.files).filter((file) =>
        file.name.toLowerCase().endsWith('.pdf')
      );
      if (pdfFiles.length === 0) {
        showNotification('error', 'Only PDF documents are supported.');
        return;
      }
      setSelectedFiles((prev) => [...prev, ...pdfFiles]);
    }
  };

  const removeSelectedFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Perform upload & auto-indexing
  const handleUploadFiles = async () => {
    if (selectedFiles.length === 0) return;
    setIsUploading(true);
    showNotification('info', `Uploading and indexing ${selectedFiles.length} document(s)...`);

    try {
      const res = await uploadFaqDocuments(selectedFiles);
      if (res.success) {
        showNotification(
          'success',
          `Successfully uploaded ${res.total_uploaded} file(s) and indexed ${res.ingest_result?.total_qa_pairs ?? res.ingest_result?.newly_indexed_docs ?? 'all'} Q&A pairs!`
        );
        setSelectedFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
        await fetchKnowledgeData();
      } else {
        showNotification('error', res.error || 'Upload completed with indexing warnings.');
      }
    } catch (err: any) {
      showNotification('error', `Upload failed: ${err.message || 'Network error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  // Delete a specific document
  const handleDeleteDocument = async (filename: string) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}" and purge its vectors from ChromaDB?`)) {
      return;
    }

    try {
      await deleteFaqDocument(filename);
      showNotification('success', `Deleted "${filename}" and purged vector embeddings.`);
      await fetchKnowledgeData();
    } catch (err: any) {
      showNotification('error', `Failed to delete "${filename}": ${err.message}`);
    }
  };

  // Refresh all existing documents in folder
  const handleReindexAll = async () => {
    if (isReindexing) return;
    setIsReindexing(true);
    showNotification('info', 'Refreshing and syncing hotel knowledge base in background...');

    try {
      const res = await ingestFaqDocuments();
      showNotification(
        'success',
        `Knowledge base refreshed! Synced ${res.total_qa_pairs.toLocaleString()} policy rules across ${res.total_pdfs} hotel documents.`
      );
      await fetchKnowledgeData();
    } catch (err: any) {
      showNotification('error', `Refresh failed: ${err.message}`);
    } finally {
      setIsReindexing(false);
    }
  };

  // Clear all documents
  const handleClearAll = async () => {
    if (
      !window.confirm(
        'WARNING: This will permanently delete ALL uploaded PDF documents from the FAQ directory and reset the ChromaDB vector database. Continue?'
      )
    ) {
      return;
    }

    setIsClearing(true);
    try {
      await clearAllFaqDocuments();
      showNotification('success', 'Knowledge base and FAQ directory completely cleared.');
      await fetchKnowledgeData();
    } catch (err: any) {
      showNotification('error', `Failed to clear knowledge base: ${err.message}`);
    } finally {
      setIsClearing(false);
    }
  };

  const filteredDocuments = documents.filter(
    (doc) =>
      doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full w-full bg-hotel-cream min-w-0 overflow-y-auto">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 sm:px-8 py-4 bg-white border-b border-stone-200 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3.5">
          <button
            onClick={onBackToChat}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-xl transition-all shadow-sm"
          >
            ← Back to Chat
          </button>
          <div>
            <h1 className="font-serif font-bold text-hotel-dark text-xl leading-tight">
              Front Office Knowledge & Document Upload
            </h1>
            <p className="text-xs text-hotel-muted">
              Upload hotel FAQ PDF documents to index policy rules, guidelines, and amenities into ChromaDB
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleReindexAll}
            disabled={isReindexing || isUploading || isClearing}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-stone-700 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 border border-stone-300 rounded-xl transition-all disabled:opacity-50 shadow-sm"
            title="Reload and refresh all hotel documents for the AI assistant"
          >
            <span className={`text-sm ${isReindexing ? 'animate-spin' : ''}`}>↻</span>
            <span>{isReindexing ? 'Refreshing Knowledge...' : 'Refresh Knowledge Base'}</span>
          </button>

          <button
            onClick={handleClearAll}
            disabled={isClearing || isUploading || totalDocsCount === 0}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-red-700 hover:text-white bg-red-50 hover:bg-red-600 border border-red-200 hover:border-red-600 rounded-xl transition-all disabled:opacity-40"
            title="Delete all uploaded documents and reset knowledge base"
          >
            <span>🗑</span>
            <span>{isClearing ? 'Clearing...' : 'Clear All'}</span>
          </button>
        </div>
      </div>

      {/* ── Notification Banner ── */}
      {notification && (
        <div
          className={`mx-6 sm:mx-8 mt-4 px-4 py-3 rounded-xl text-xs font-medium flex items-center justify-between shadow-sm animate-fadeIn ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border border-emerald-300'
              : notification.type === 'error'
              ? 'bg-red-50 text-red-900 border border-red-300'
              : 'bg-amber-50 text-amber-900 border border-amber-300'
          }`}
        >
          <span>{notification.text}</span>
          <button
            onClick={() => setNotification(null)}
            className="text-stone-500 hover:text-stone-900 font-bold ml-3"
          >
            ✕
          </button>
        </div>
      )}

      <div className="p-6 sm:p-8 max-w-6xl mx-auto w-full space-y-6">
        {/* ── Key Metrics Cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-sm flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-xl">
              📄
            </div>
            <div>
              <p className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                PDF Documents
              </p>
              <p className="text-2xl font-bold text-hotel-dark">
                {totalDocsCount.toLocaleString()}
              </p>
              <p className="text-[10px] text-stone-400">Files in FAQ directory</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-sm flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-xl">
              ⚡
            </div>
            <div>
              <p className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                Active Knowledge Rules
              </p>
              <p className="text-2xl font-bold text-hotel-dark">
                {(collectionCount || totalQaCount).toLocaleString()}
              </p>
              <p className="text-[10px] text-stone-400">Ready for instant AI search</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-sm flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-xl">
              🏷️
            </div>
            <div>
              <p className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                Policy Categories
              </p>
              <p className="text-2xl font-bold text-hotel-dark">
                {totalDocsCount > 0 ? (knowledgeStatus?.faq_documents?.total_categories ?? totalDocsCount) : 0}
              </p>
              <p className="text-[10px] text-stone-400">Structured topic areas</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-sm flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-xl">
              🔍
            </div>
            <div>
              <p className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                Embedding Model
              </p>
              <p className="text-sm font-bold text-hotel-dark truncate max-w-[140px]" title="MiniLM-L6-v2">
                all-MiniLM-L6-v2
              </p>
              <p className="text-[10px] text-stone-400">Dense Semantic Search</p>
            </div>
          </div>
        </div>

        {/* ── Upload Area ── */}
        <div className="bg-white rounded-2xl p-6 border border-stone-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg">📤</span>
              <h2 className="font-semibold text-stone-900 text-sm">
                Upload New FAQ Documents (PDF)
              </h2>
            </div>
            <span className="text-xs text-stone-500">
              Multiple PDF files supported
            </span>
          </div>

          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-amber-500 bg-amber-50/60 scale-[0.99]'
                : 'border-stone-300 hover:border-hotel-gold hover:bg-stone-50/60'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,application/pdf"
              onChange={handleFileInputChange}
              className="hidden"
            />
            <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-100 border border-amber-300 flex items-center justify-center text-2xl mb-3 shadow-inner">
              📂
            </div>
            <p className="text-sm font-semibold text-stone-800">
              Drag & drop your hotel FAQ PDF documents here
            </p>
            <p className="text-xs text-stone-500 mt-1">
              or <span className="text-amber-700 font-bold underline">browse from your computer</span>
            </p>
            <p className="text-[11px] text-stone-400 mt-3">
              Supports standard hotel FAQ format (Q&A numbered pairs or Q: / A: layout)
            </p>
          </div>

          {/* ── Selected files staging ── */}
          {selectedFiles.length > 0 && (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-stone-700">
                  Ready to upload ({selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''}):
                </p>
                <button
                  onClick={() => setSelectedFiles([])}
                  className="text-xs text-stone-500 hover:text-stone-800 underline"
                >
                  Clear Selection
                </button>
              </div>

              <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1">
                {selectedFiles.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between px-3 py-2 bg-white rounded-lg border border-stone-200 text-xs shadow-2xs"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="text-red-500 font-bold">PDF</span>
                      <span className="font-medium text-stone-800 truncate">{f.name}</span>
                      <span className="text-stone-400 text-[10px]">
                        ({(f.size / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSelectedFile(i);
                      }}
                      className="text-stone-400 hover:text-red-600 font-bold px-1.5"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleUploadFiles}
                  disabled={isUploading}
                  className="flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white rounded-xl text-xs font-bold transition-all shadow-md active:scale-95 disabled:opacity-50"
                >
                  {isUploading ? (
                    <>
                      <span className="animate-spin">↻</span>
                      <span>Uploading & Vector Indexing...</span>
                    </>
                  ) : (
                    <>
                      <span>⬆</span>
                      <span>Upload & Index Documents</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Document List & Status ── */}
        <div className="bg-white rounded-2xl border border-stone-200 shadow-sm overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-stone-200 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-stone-900 text-sm">
                Indexed FAQ Documents ({filteredDocuments.length})
              </h2>
              <p className="text-xs text-stone-500">
                Documents currently active in the front desk RAG knowledge base
              </p>
            </div>

            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search documents or categories..."
                className="text-xs bg-stone-50 border border-stone-300 rounded-xl px-3.5 py-1.5 pl-8 text-stone-800 placeholder-stone-400 outline-none focus:border-hotel-gold w-64"
              />
              <span className="absolute left-2.5 top-2 text-stone-400 text-xs">🔍</span>
            </div>
          </div>

          {isLoading ? (
            <div className="p-12 text-center text-stone-400 text-xs">
              <span className="animate-spin inline-block text-xl mb-2">↻</span>
              <p>Loading document registry...</p>
            </div>
          ) : filteredDocuments.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-stone-50/80 border-b border-stone-200 text-stone-500 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3 px-4">Document Name</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4 text-center">Extracted Q&As</th>
                    <th className="py-3 px-4">File Size</th>
                    <th className="py-3 px-4">Last Indexed</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {filteredDocuments.map((doc) => (
                    <tr key={doc.filename} className="hover:bg-amber-50/30 transition-colors group">
                      <td className="py-3 px-4 font-medium text-stone-900">
                        <div className="flex items-center gap-2">
                          <span className="text-red-500 text-sm">📄</span>
                          <span className="truncate max-w-xs" title={doc.filename}>
                            {doc.filename}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-900 border border-amber-300/60">
                          {doc.category}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center font-bold text-stone-700">
                        {doc.qa_count > 0 ? (
                          <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-200">
                            {doc.qa_count} pairs
                          </span>
                        ) : (
                          <span className="text-stone-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-stone-500">{doc.formatted_size}</td>
                      <td className="py-3 px-4 text-stone-400 text-[11px]">
                        {doc.last_indexed
                          ? new Date(doc.last_indexed).toLocaleDateString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'Pending'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleDeleteDocument(doc.filename)}
                          className="px-2.5 py-1 text-[11px] font-semibold text-red-600 hover:text-white bg-red-50 hover:bg-red-600 border border-red-200 rounded-lg transition-all"
                          title="Delete file and delete vector embeddings"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center space-y-3">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-stone-100 flex items-center justify-center text-2xl">
                📂
              </div>
              <p className="text-sm font-semibold text-stone-700">No FAQ documents found</p>
              <p className="text-xs text-stone-500 max-w-md mx-auto">
                The knowledge base is currently clean. Upload your hotel PDF files above to automatically extract and index operational policies and rules into ChromaDB.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
