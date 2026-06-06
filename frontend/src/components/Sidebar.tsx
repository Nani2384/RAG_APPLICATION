"use client";
import { UploadCloud, Settings, Database, MessageSquare, Plus, LogOut, Folder, Loader2, X } from "lucide-react";
import React, { useEffect, useState } from "react";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  activeThreadId: number | null;
  setActiveThreadId: (id: number | null) => void;
  activeWorkspaceId: number | null;
  setActiveWorkspaceId: (id: number) => void;
  token: string;
  onAuthError: () => void;
  onLogout: () => void;
}

interface ThreadItem {
  id: number;
  title: string;
  created_at: string | null;
}

interface WorkspaceItem {
  id: number;
  name: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function Sidebar({
  activeTab,
  setActiveTab,
  activeThreadId,
  setActiveThreadId,
  activeWorkspaceId,
  setActiveWorkspaceId,
  token,
  onAuthError,
  onLogout
}: SidebarProps) {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [isCreatingWorkspace, setIsCreatingWorkspace] = useState(false);

  const fetchWorkspaces = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/workspaces`, {
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
        const list = data.data || [];
        setWorkspaces(list);
        
        // Auto select first workspace if none is active
        if (list.length > 0 && !activeWorkspaceId) {
          const savedWs = localStorage.getItem("active_workspace_id");
          const savedWsId = savedWs ? parseInt(savedWs, 10) : null;
          if (savedWsId && list.some((w: WorkspaceItem) => w.id === savedWsId)) {
            setActiveWorkspaceId(savedWsId);
          } else {
            setActiveWorkspaceId(list[0].id);
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch workspaces", e);
    }
  };

  const fetchThreads = async () => {
    if (!token || !activeWorkspaceId) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/threads?workspace_id=${activeWorkspaceId}`, {
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
        setThreads(data.data || []);
      }
    } catch (e) {
      console.error("Failed to fetch threads", e);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, [token]);

  useEffect(() => {
    if (activeTab === "conversations" && activeWorkspaceId) {
      fetchThreads();
    } else if (!activeWorkspaceId) {
      setThreads([]);
    }
  }, [activeTab, activeThreadId, activeWorkspaceId, token]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim() || isCreatingWorkspace || !token) return;
    setIsCreatingWorkspace(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/workspaces/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ name: newWorkspaceName.trim() })
      });
      if (res.status === 401) {
        onAuthError();
        return;
      }
      if (res.ok) {
        const newWs = await res.json();
        setNewWorkspaceName("");
        setIsCreateModalOpen(false);
        await fetchWorkspaces();
        setActiveWorkspaceId(newWs.id);
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to create workspace");
      }
    } catch (e) {
      console.error("Error creating workspace", e);
      alert("Error connecting to server.");
    } finally {
      setIsCreatingWorkspace(false);
    }
  };

  return (
    <div className="w-64 bg-slate-950 h-full flex flex-col pt-4 shrink-0 text-slate-200 relative">
      <div className="px-6 pb-6 border-b border-slate-800 flex items-center justify-between">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent inline-flex items-center gap-2">
          <Database className="w-5 h-5 text-indigo-400" /> Nexus RAG
        </h1>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-2 px-3">
        {/* Workspaces Header */}
        <div className="flex items-center justify-between px-3 mb-1 mt-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Workspaces</span>
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            title="Create Workspace"
            className="p-1 bg-slate-900 hover:bg-slate-800 text-indigo-400 hover:text-indigo-300 rounded border border-white/5 cursor-pointer transition-colors"
          >
            <Plus size={14} />
          </button>
        </div>

        {/* Workspaces List */}
        <div className="flex flex-col gap-1 px-1 max-h-[180px] overflow-y-auto scrollbar-thin mb-3">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => setActiveWorkspaceId(ws.id)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors w-full text-left cursor-pointer ${
                activeWorkspaceId === ws.id
                  ? "bg-indigo-500/15 text-indigo-300 border-l-2 border-indigo-500 font-semibold"
                  : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200"
              }`}
            >
              <Folder size={14} className={activeWorkspaceId === ws.id ? "text-indigo-400" : "text-slate-500"} />
              <span className="truncate">{ws.name}</span>
            </button>
          ))}
          {workspaces.length === 0 && (
            <span className="text-[10px] text-slate-600 px-3 py-1 italic">No workspaces found</span>
          )}
        </div>

        {/* Conversations Header */}
        <div className="flex items-center justify-between px-3 mb-1 border-t border-slate-900 pt-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Conversations</span>
          {activeWorkspaceId && (
            <button 
              onClick={() => {
                setActiveTab("conversations");
                setActiveThreadId(null);
              }}
              title="Start New Chat"
              className="p-1 bg-slate-900 hover:bg-slate-800 text-indigo-400 hover:text-indigo-300 rounded border border-white/5 cursor-pointer transition-colors"
            >
              <Plus size={14} />
            </button>
          )}
        </div>

        {activeWorkspaceId && (
          <SidebarItem 
            icon={<MessageSquare size={18} />} 
            label="New Chat" 
            active={activeTab === "conversations" && activeThreadId === null} 
            onClick={() => {
              setActiveTab("conversations");
              setActiveThreadId(null);
            }}
          />
        )}

        {activeWorkspaceId && threads.length > 0 && activeTab === "conversations" && (
          <div className="flex flex-col gap-1 pl-4 mt-1 max-h-[220px] overflow-y-auto border-l border-slate-800 ml-5 pr-1">
            {threads.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setActiveTab("conversations");
                  setActiveThreadId(t.id);
                }}
                className={`text-left px-3 py-2 rounded-md text-xs truncate max-w-full font-medium transition-colors cursor-pointer ${
                  activeThreadId === t.id
                    ? "bg-indigo-500/20 text-indigo-300 border-l border-indigo-550"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                }`}
              >
                {t.title}
              </button>
            ))}
          </div>
        )}

        <div className="h-px bg-slate-900 my-2" />

        <SidebarItem 
          icon={<UploadCloud size={18} />} 
          label="Ingestion Jobs" 
          active={activeTab === "ingestion"} 
          onClick={() => setActiveTab("ingestion")}
        />
      </div>

      <div className="p-4 border-t border-slate-800 flex flex-col gap-2">
        <SidebarItem 
          icon={<Settings size={18} />} 
          label="Settings" 
          active={activeTab === "settings"} 
          onClick={() => setActiveTab("settings")}
        />
        <button
          onClick={onLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors w-full cursor-pointer text-slate-500 hover:bg-rose-500/10 hover:text-rose-450"
        >
          <LogOut size={18} />
          <span>Sign Out</span>
        </button>
      </div>

      {/* Glassmorphic Workspace Creation Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 relative overflow-hidden">
            <button 
              onClick={() => setIsCreateModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <X size={18} />
            </button>
            <h3 className="text-base font-bold text-slate-200 mb-2">Create Workspace</h3>
            <p className="text-xs text-slate-400 mb-4">
              Organize related conversations and documents into isolated workspaces.
            </p>
            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <input
                type="text"
                value={newWorkspaceName}
                onChange={(e) => setNewWorkspaceName(e.target.value)}
                placeholder="Workspace name (e.g. Finance RAG)"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-2.5 px-4 text-sm text-slate-200 outline-none focus:border-indigo-500/50 transition-all font-medium"
                required
                autoFocus
              />
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-350 text-xs font-semibold rounded-xl transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingWorkspace || !newWorkspaceName.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 cursor-pointer shadow-md hover:shadow-indigo-500/10"
                >
                  {isCreatingWorkspace ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <span>Create</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function SidebarItem({ icon, label, active = false, onClick }: SidebarItemProps) {
  return (
    <button 
      onClick={onClick}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors w-full cursor-pointer ${
        active 
          ? "bg-indigo-500/10 text-indigo-400 font-medium" 
          : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

