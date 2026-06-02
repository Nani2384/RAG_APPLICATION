"use client";
import { FolderKanban, UploadCloud, Settings, Database, MessageSquare, Plus, LogOut } from "lucide-react";
import { useEffect, useState } from "react";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  activeThreadId: number | null;
  setActiveThreadId: (id: number | null) => void;
  token: string;
  onAuthError: () => void;
  onLogout: () => void;
}

interface ThreadItem {
  id: number;
  title: string;
  created_at: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function Sidebar({ activeTab, setActiveTab, activeThreadId, setActiveThreadId, token, onAuthError, onLogout }: SidebarProps) {
  const [threads, setThreads] = useState<ThreadItem[]>([]);

  const fetchThreads = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/threads?workspace_id=1`, {
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
    if (activeTab === "conversations") {
      fetchThreads();
    }
  }, [activeTab, activeThreadId, token]);

  return (
    <div className="w-64 bg-slate-950 h-full flex flex-col pt-4 shrink-0 text-slate-200">
      <div className="px-6 pb-6 border-b border-slate-800 flex items-center justify-between">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent inline-flex items-center gap-2">
          <Database className="w-5 h-5 text-indigo-400" /> Nexus RAG
        </h1>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-2 px-3">
        <div className="flex items-center justify-between px-3 mb-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Workspace 1</span>
          <button 
            onClick={() => {
              setActiveTab("conversations");
              setActiveThreadId(null);
            }}
            title="Start New Chat"
            className="p-1 bg-slate-900 hover:bg-slate-800 text-indigo-400 hover:text-indigo-300 rounded border border-white/5 cursor-pointer"
          >
            <Plus size={14} />
          </button>
        </div>

        <SidebarItem 
          icon={<MessageSquare size={18} />} 
          label="New Chat" 
          active={activeTab === "conversations" && activeThreadId === null} 
          onClick={() => {
            setActiveTab("conversations");
            setActiveThreadId(null);
          }}
        />

        {threads.length > 0 && activeTab === "conversations" && (
          <div className="flex flex-col gap-1 pl-4 mt-2 max-h-[250px] overflow-y-auto border-l border-slate-800 ml-5 pr-1">
            {threads.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setActiveTab("conversations");
                  setActiveThreadId(t.id);
                }}
                className={`text-left px-3 py-2 rounded-md text-xs truncate max-w-full font-medium transition-colors cursor-pointer ${
                  activeThreadId === t.id
                    ? "bg-indigo-500/20 text-indigo-300 border-l border-indigo-500"
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
          icon={<FolderKanban size={18} />} 
          label="Workspaces" 
          active={activeTab === "workspaces"} 
          onClick={() => setActiveTab("workspaces")}
        />
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
          ? "bg-indigo-500/10 text-indigo-400" 
          : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
