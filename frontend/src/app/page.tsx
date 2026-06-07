"use client";

import { useState, useEffect } from "react";
import { ChatInterface } from "@/components/ChatInterface";
import { Sidebar } from "@/components/Sidebar";
import { IngestionDashboard } from "@/components/IngestionDashboard";
import { Loader2, Key, ShieldAlert, Sparkles, User, Mail, ArrowRight } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [activeTab, setActiveTab] = useState("conversations");
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  
  // Auth state management
  const [token, setToken] = useState<string>("");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  
  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [authSuccessMsg, setAuthSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("jwt_token");
    setToken(saved || "dummy-token-123");
    const savedWs = localStorage.getItem("active_workspace_id");
    if (savedWs) {
      setActiveWorkspaceId(parseInt(savedWs, 10));
    }
  }, []);

  const handleSelectWorkspace = (id: number) => {
    setActiveWorkspaceId(id);
    localStorage.setItem("active_workspace_id", id.toString());
    setActiveThreadId(null);
  };

  const handleAuthError = () => {
    setAuthError("Your active session has expired or requires validation. Please sign in.");
    setShowAuthModal(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    setToken("dummy-token-123");
    setAuthSuccessMsg("Logged out. Returned to developer bypass mode.");
    setTimeout(() => setAuthSuccessMsg(null), 3000);
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccessMsg(null);

    const endpoint = isRegisterMode ? "/api/v1/auth/register" : "/api/v1/auth/login";

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication request failed.");
      }

      if (isRegisterMode) {
        setAuthSuccessMsg("Account registered successfully! You can now log in.");
        setIsRegisterMode(false);
        setPassword("");
      } else {
        const tokenVal = data.access_token;
        localStorage.setItem("jwt_token", tokenVal);
        setToken(tokenVal);
        setShowAuthModal(false);
        setAuthSuccessMsg("Signed in successfully!");
        setEmail("");
        setPassword("");
        setTimeout(() => setAuthSuccessMsg(null), 3000);
      }
    } catch (err: any) {
      setAuthError(err.message || "Something went wrong. Please check your credentials.");
    } finally {
      setAuthLoading(false);
    }
  };

  const useDeveloperBypass = () => {
    localStorage.removeItem("jwt_token");
    setToken("dummy-token-123");
    setShowAuthModal(false);
    setAuthError(null);
    setAuthSuccessMsg("Developer bypass mode enabled.");
    setTimeout(() => setAuthSuccessMsg(null), 3000);
  };

  return (
    <main className="flex h-screen w-full relative overflow-hidden bg-slate-900 font-sans">
      {/* Toast Alert Notifications */}
      {authSuccessMsg && (
        <div className="absolute top-4 right-4 z-50 bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 backdrop-blur-md transition-all animate-bounce">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></div>
          <span className="text-xs font-semibold">{authSuccessMsg}</span>
        </div>
      )}

      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        activeThreadId={activeThreadId}
        setActiveThreadId={setActiveThreadId}
        activeWorkspaceId={activeWorkspaceId}
        setActiveWorkspaceId={handleSelectWorkspace}
        token={token}
        onAuthError={handleAuthError}
        onLogout={handleLogout}
      />
      <div className="flex-1 flex flex-col h-full bg-slate-900 border-l border-white/5 overflow-hidden">
        {activeTab === "conversations" && (
          <ChatInterface 
            activeThreadId={activeThreadId} 
            setActiveThreadId={setActiveThreadId} 
            activeWorkspaceId={activeWorkspaceId}
            token={token}
            onAuthError={handleAuthError}
          />
        )}
        {activeTab === "ingestion" && (
          <IngestionDashboard 
            token={token}
            activeWorkspaceId={activeWorkspaceId}
            onAuthError={handleAuthError}
          />
        )}
        {(activeTab === "workspaces" || activeTab === "settings") && (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 bg-slate-900 relative">
            {/* Elegant Background Glow */}
            <div className="absolute w-[300px] h-[300px] rounded-full bg-indigo-500/5 blur-[80px] pointer-events-none"></div>
            <h2 className="text-lg font-medium text-slate-400 mb-1">Coming Soon</h2>
            <p className="text-sm text-slate-600">The {activeTab} dashboard is currently under development.</p>
          </div>
        )}
      </div>

      {/* Modern Glassmorphic Auth Modal */}
      {(showAuthModal || !token) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-fade-in">
          <div className="w-full max-w-md bg-slate-800/80 border border-white/10 rounded-3xl shadow-2xl p-8 relative overflow-hidden backdrop-blur-xl">
            {/* Ambient background decoration */}
            <div className="absolute -top-16 -left-16 w-32 h-32 rounded-full bg-indigo-500/10 blur-2xl"></div>
            <div className="absolute -bottom-16 -right-16 w-32 h-32 rounded-full bg-indigo-500/10 blur-2xl"></div>

            <div className="flex flex-col items-center text-center mb-6">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-3">
                <Key className="w-6 h-6 text-indigo-400" />
              </div>
              <h3 className="text-xl font-bold text-slate-100 flex items-center gap-1.5 justify-center">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
                {isRegisterMode ? "Create Secure Account" : "Access RAG Platform"}
              </h3>
              <p className="text-xs text-slate-400 mt-1 max-w-[280px]">
                {isRegisterMode 
                  ? "Sign up to seed your personal multi-tenant workspaces" 
                  : "Sign in using your registered email credentials"}
              </p>
            </div>

            {authError && (
              <div className="mb-5 bg-rose-500/10 border border-rose-500/20 text-rose-400 p-3.5 rounded-xl text-xs flex items-start gap-2.5">
                <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                <span>{authError}</span>
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3.5 w-4.5 h-4.5 text-slate-500" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-xl py-3 pl-11 pr-4 text-sm text-slate-200 outline-none focus:border-indigo-500/50 transition-all font-medium"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Password</label>
                <div className="relative">
                  <Key className="absolute left-3.5 top-3.5 w-4.5 h-4.5 text-slate-500" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-xl py-3 pl-11 pr-4 text-sm text-slate-200 outline-none focus:border-indigo-500/50 transition-all font-medium"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-indigo-500/20 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {authLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <span>{isRegisterMode ? "Register & Seed" : "Authenticate"}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <div className="relative flex py-4 items-center">
              <div className="flex-grow border-t border-slate-700/50"></div>
              <span className="flex-shrink mx-4 text-[10px] text-slate-500 uppercase tracking-widest font-bold">Or</span>
              <div className="flex-grow border-t border-slate-700/50"></div>
            </div>

            <div className="space-y-3">
              <button
                onClick={useDeveloperBypass}
                className="w-full py-2.5 px-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-700/60 hover:border-slate-600 text-slate-300 font-medium text-xs rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <User className="w-4 h-4 text-indigo-400" />
                <span>Developer Bypass (Dummy Session)</span>
              </button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsRegisterMode(!isRegisterMode);
                    setAuthError(null);
                  }}
                  className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors font-semibold"
                >
                  {isRegisterMode ? "Already have an account? Sign In" : "Need a tenant? Create an account"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
