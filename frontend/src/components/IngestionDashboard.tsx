"use client";

import { useState, useEffect } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, RefreshCw, Sparkles } from "lucide-react";

interface DocumentItem {
  id: number;
  filename: string;
  status: "uploaded" | "processing" | "indexed" | "error";
  workspace_id: number;
  created_at: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface IngestionDashboardProps {
  token: string;
  onAuthError: () => void;
}

export function IngestionDashboard({ token, onAuthError }: IngestionDashboardProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const fetchDocuments = async () => {
    if (!token) return;
    setIsRefreshing(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/documents/`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.status === 401) {
        onAuthError();
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.data || []);
      }
    } catch (e) {
      console.error("Failed to fetch documents", e);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDocuments();

    // Auto poll if any document is in transition state
    const interval = setInterval(() => {
      const hasTransitioning = documents.some(
        (doc) => doc.status === "uploaded" || doc.status === "processing"
      );
      if (hasTransitioning || documents.length === 0) {
        fetchDocuments();
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [documents]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await uploadFile(e.target.files[0]);
    }
  };

  const uploadFile = async (file: File) => {
    if (!token) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/v1/documents/upload`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData,
      });

      if (res.status === 401) {
        onAuthError();
        return;
      }

      if (res.ok) {
        await fetchDocuments();
      } else {
        alert("Upload failed. Make sure the backend service is active.");
      }
    } catch (e) {
      console.error("Upload failed", e);
      alert("Error connecting to server.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-900 text-slate-100 overflow-y-auto">
      {/* Header */}
      <div className="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-slate-950/40 backdrop-blur-md shrink-0">
        <h2 className="text-lg font-medium text-slate-200 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-400" /> Document Ingestion Control Room
        </h2>
        <button
          onClick={fetchDocuments}
          disabled={isRefreshing}
          className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors border border-white/5 disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="flex-1 p-8 max-w-5xl w-full mx-auto flex flex-col gap-8">
        {/* Upload Box */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center transition-all ${
            dragActive
              ? "border-indigo-500 bg-indigo-500/10 scale-[1.01]"
              : "border-slate-800 bg-slate-800/40 hover:border-slate-700"
          }`}
        >
          <input
            type="file"
            id="file-upload"
            className="hidden"
            onChange={handleFileChange}
            disabled={isUploading}
          />
          <label
            htmlFor="file-upload"
            className="flex flex-col items-center cursor-pointer group"
          >
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4 group-hover:bg-indigo-600/20 group-hover:scale-110 transition-all">
              {isUploading ? (
                <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
              ) : (
                <UploadCloud className="w-8 h-8 text-indigo-400 group-hover:text-indigo-300 transition-colors" />
              )}
            </div>
            <span className="text-sm font-medium text-slate-300">
              {isUploading ? "Uploading file..." : "Drag & Drop document or Click to Browse"}
            </span>
            <span className="text-xs text-slate-500 mt-2">
              Supports PDF, PPTX, DOCX, TXT, HTML (Max 50MB)
            </span>
          </label>
        </div>

        {/* Documents Table */}
        <div className="flex-1 flex flex-col min-h-[300px]">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Ingestion Pipeline Status
          </h3>

          <div className="bg-slate-950/40 border border-white/5 rounded-2xl overflow-hidden flex-1 shadow-2xl">
            {documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                <FileText className="w-12 h-12 mb-3 stroke-[1.5] text-slate-600" />
                <p className="text-sm">No documents in the system database.</p>
                <p className="text-xs mt-1 text-slate-600">Upload a document to index it into FAISS/Pinecone.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/5 text-xs font-semibold text-slate-400 uppercase bg-slate-900/40">
                      <th className="px-6 py-4">Document ID</th>
                      <th className="px-6 py-4">File Name</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Workspace ID</th>
                      <th className="px-6 py-4 text-right">Added At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-sm">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-slate-800/20 transition-colors">
                        <td className="px-6 py-4 font-mono text-slate-400 text-xs">#{doc.id}</td>
                        <td className="px-6 py-4 font-medium text-slate-200">{doc.filename}</td>
                        <td className="px-6 py-4">
                          <StatusBadge doc={doc} onRetrySuccess={fetchDocuments} token={token} onAuthError={onAuthError} />
                        </td>
                        <td className="px-6 py-4 text-slate-400 text-xs">Workspace {doc.workspace_id}</td>
                        <td className="px-6 py-4 text-slate-400 text-xs text-right">
                          {doc.created_at ? new Date(doc.created_at).toLocaleString() : "Just now"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface IngestionDashboardDoc extends DocumentItem {
  metadata_json?: string | object | null;
}

function StatusBadge({ doc, onRetrySuccess, token, onAuthError }: { doc: IngestionDashboardDoc; onRetrySuccess: () => void; token: string; onAuthError: () => void }) {
  const [isRetrying, setIsRetrying] = useState(false);
  const status = doc.status;
  
  const meta = doc.metadata_json 
    ? (typeof doc.metadata_json === "string" ? JSON.parse(doc.metadata_json) : doc.metadata_json) as any
    : {};

  const handleRetry = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) return;
    setIsRetrying(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/documents/${doc.id}/retry`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.status === 401) {
        onAuthError();
        return;
      }
      if (res.ok) {
        onRetrySuccess();
      } else {
        alert("Failed to queue ingestion retry job.");
      }
    } catch (err) {
      console.error("Retry failed", err);
      alert("Error connecting to server.");
    } finally {
      setIsRetrying(false);
    }
  };

  switch (status) {
    case "indexed":
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> Indexed
        </span>
      );
    case "processing":
      const retryText = meta.current_retry 
        ? ` (Retry ${meta.current_retry}/3)`
        : "";
      return (
        <span 
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20" 
          title={meta.error ? `Last transient error: ${meta.error}` : "Parsing and indexing document..."}
        >
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Processing{retryText}
        </span>
      );
    case "uploaded":
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Uploaded
        </span>
      );
    case "error":
      const errTitle = meta.error_type || "Index Failure";
      const errDetails = meta.error_details || meta.error || "An unexpected ingestion error occurred.";
      const troubleshooting = meta.troubleshooting || "Please check container logs for troubleshooting.";
      
      return (
        <div className="flex flex-col gap-1.5 items-start">
          <span 
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20 cursor-help"
            title={`${errTitle}\n\nDetails: ${errDetails}\n\nTroubleshooting: ${troubleshooting}`}
          >
            <AlertCircle className="w-3.5 h-3.5" /> {errTitle}
          </span>
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            className="text-[10px] text-indigo-400 hover:text-indigo-300 font-semibold bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 px-2.5 py-1 rounded-lg transition-all cursor-pointer disabled:opacity-50 inline-flex items-center gap-1"
          >
            {isRetrying ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : null}
            Retry Ingestion
          </button>
        </div>
      );
  }
}
