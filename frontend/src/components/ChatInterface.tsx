"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Sparkles, FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: any[];
}

interface ChatInterfaceProps {
  activeThreadId: number | null;
  setActiveThreadId: (id: number | null) => void;
  activeWorkspaceId: number | null;
  token: string;
  onAuthError: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function FormattedMessage({ 
  content, 
  setExpandedSourceIdx 
}: { 
  content: string; 
  setExpandedSourceIdx: (idx: number | null) => void;
}) {
  // Translate [^N^] citation markers cleanly to standard markdown links [N](#source-N)
  const processedContent = content.replace(/\[\^(\d+)\^\]/g, "[$1](#source-$1)");

  return (
    <div className="prose prose-invert max-w-none text-slate-300 leading-relaxed break-words text-sm md:text-[15px]">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const match = href?.match(/^#source-(\d+)$/);
            if (match) {
              const idx = parseInt(match[1], 10);
              return (
                <a
                  href={href}
                  onClick={(e) => {
                    e.preventDefault();
                    // Toggle the collapsible preview open
                    setExpandedSourceIdx(idx);
                    // Smoothly scroll to the target pill and flash highlight
                    setTimeout(() => {
                      const el = document.getElementById(`pill-${idx}`);
                      if (el) {
                        el.scrollIntoView({ behavior: "smooth", block: "center" });
                        el.classList.add("bg-indigo-500/40", "border-indigo-400");
                        setTimeout(() => {
                          el.classList.remove("bg-indigo-500/40", "border-indigo-400");
                        }, 1200);
                      }
                    }, 100);
                  }}
                  className="inline-flex items-center justify-center px-1.5 py-0.25 mx-0.5 text-[9px] font-extrabold bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 border border-indigo-500/30 rounded cursor-pointer transition-colors align-super select-none hover:no-underline font-mono"
                  title={`Expand and View Source #${idx}`}
                >
                  {idx}
                </a>
              );
            }
            return (
              <a 
                href={href} 
                target="_blank" 
                rel="noreferrer" 
                className="text-indigo-400 hover:text-indigo-300 underline font-medium transition-colors"
              >
                {children}
              </a>
            );
          },
          h1: ({ children }) => <h1 className="text-xl font-bold text-slate-100 mt-5 mb-2.5 border-b border-slate-700/50 pb-1 flex items-center gap-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold text-slate-200 mt-4 mb-2 flex items-center gap-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold text-slate-300 mt-3.5 mb-1.5">{children}</h3>,
          p: ({ children }) => <p className="mb-3.5 leading-relaxed text-slate-300 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-3.5 space-y-1.5 text-slate-350">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-3.5 space-y-1.5 text-slate-350">{children}</ol>,
          li: ({ children }) => <li className="leading-normal">{children}</li>,
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            const inline = !className;
            return !inline ? (
              <pre className="bg-slate-900 border border-slate-800 rounded-xl p-4 my-3.5 overflow-x-auto text-xs font-mono text-slate-300 scrollbar-thin select-text">
                <code className={className} {...props}>{children}</code>
              </pre>
            ) : (
              <code className="bg-slate-900/60 px-1.5 py-0.5 rounded text-xs font-mono text-indigo-300 border border-slate-700/40" {...props}>{children}</code>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 rounded-xl border border-slate-750/80">
              <table className="w-full text-sm text-left border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-900/60 text-xs uppercase text-slate-400 border-b border-slate-750">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-slate-800">{children}</tbody>,
          tr: ({ children }) => <tr className="hover:bg-slate-850/20 transition-colors">{children}</tr>,
          th: ({ children }) => <th className="px-4 py-2.5 font-semibold text-slate-300">{children}</th>,
          td: ({ children }) => <td className="px-4 py-2.5 text-slate-300">{children}</td>,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}

export function ChatInterface({ activeThreadId, setActiveThreadId, activeWorkspaceId, token, onAuthError }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I am your enterprise AI assistant. I have access to your workspace documents. How can I help you today?" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSourceIdx, setExpandedSourceIdx] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (activeThreadId !== null && token) {
      if (isLoading) return; // Prevent duplicate fetch during active streaming session
      setIsLoading(true);
      fetch(`${API_BASE}/api/v1/chat/threads/${activeThreadId}/messages`, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      })
        .then((res) => {
          if (res.status === 401) {
            onAuthError();
            throw new Error("Unauthorized");
          }
          return res.json();
        })
        .then((data) => {
          const msgs = data.data || [];
          setMessages(
            msgs.map((m: any) => ({
              role: m.role as "user" | "assistant",
              content: m.content,
              sources: m.sources,
            }))
          );
        })
        .catch((e) => console.error("Error loading chat messages", e))
        .finally(() => setIsLoading(false));
    } else {
      setMessages([
        { role: "assistant", content: "Hello! I am your enterprise AI assistant. I have access to your workspace documents. How can I help you today?" }
      ]);
    }
  }, [activeThreadId, token]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/completions`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          query: userMessage.content,
          workspace_id: activeWorkspaceId || 1,
          thread_id: activeThreadId,
          chat_history: messages
            .filter((m) => m.content !== "Hello! I am your enterprise AI assistant. I have access to your workspace documents. How can I help you today?")
            .slice(-5)
            .map((m) => ({ role: m.role, content: m.content }))
        })
      });

      if (res.status === 401) {
        onAuthError();
        setIsLoading(false);
        return;
      }

      if (!res.body) throw new Error("No body");
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      
      let assistantMsg: Message = { role: "assistant", content: "", sources: [] };
      setMessages((prev) => [...prev, assistantMsg]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            if (dataStr === "[DONE]") break;
            
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === "thread_id") {
                setActiveThreadId(parsed.data);
              } else if (parsed.type === "sources") {
                assistantMsg.sources = parsed.data;
              } else if (parsed.type === "content") {
                assistantMsg.content += parsed.data;
              }
              
              if (parsed.type === "sources" || parsed.type === "content") {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1] = { ...assistantMsg };
                  return newMsgs;
                });
              }
            } catch (e) {
              console.error("Failed to parse stream JSON", e);
            }
          }
        }
      }
    } catch (e) {
      console.error(e);
      setTimeout(() => {
        setMessages((prev) => [...prev, { role: "assistant", content: "Error connecting to backend API. Please make sure the FastAPI server is running." }]);
      }, 500);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full relative">
      {/* Header */}
      <div className="h-16 border-b border-white/5 flex items-center px-6 backdrop-blur-md absolute top-0 w-full z-10 bg-slate-900/80">
        <h2 className="text-lg font-medium text-slate-200 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-400" /> Project Alpha Chat
        </h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto pt-20 pb-24 px-4 sm:px-6 md:px-12 lg:px-24">
        <div className="max-w-4xl mx-auto flex flex-col gap-8">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0 border border-indigo-500/30">
                  <Bot className="w-5 h-5 text-indigo-400" />
                </div>
              )}
              
              <div className={`p-4 rounded-2xl max-w-[85%] ${
                msg.role === "user" 
                  ? "bg-indigo-600 text-white rounded-br-none" 
                  : "bg-slate-800 text-slate-200 rounded-bl-none shadow-xl border border-white/5"
              }`}>
                {msg.role === "assistant" ? (
                  <FormattedMessage content={msg.content} setExpandedSourceIdx={setExpandedSourceIdx} />
                ) : (
                  <div className="text-sm md:text-base leading-relaxed">{msg.content}</div>
                )}
                
                {/* Sources & Context Horizontal Pills UI */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3.5 border-t border-slate-700/40">
                    <div className="flex flex-wrap gap-2 items-center">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1.5">Sources & Grounding:</span>
                      {msg.sources.map((src, idx) => {
                        const citIdx = src.citation_idx || (idx + 1);
                        const isExpanded = expandedSourceIdx === citIdx;
                        return (
                          <button
                            key={idx}
                            id={`pill-${citIdx}`}
                            onClick={() => setExpandedSourceIdx(isExpanded ? null : citIdx)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium border transition-all duration-200 select-none ${
                              isExpanded
                                ? "bg-indigo-500/25 text-indigo-300 border-indigo-500/45 shadow-sm shadow-indigo-500/5 hover:bg-indigo-500/30"
                                : "bg-slate-900/60 hover:bg-slate-850 text-slate-350 border-slate-700/60"
                            }`}
                          >
                            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-extrabold ${
                              isExpanded ? "bg-indigo-500 text-white" : "bg-slate-800 text-slate-400 border border-slate-700/50"
                            }`}>
                              {citIdx}
                            </span>
                            <FileText className="w-3.5 h-3.5 text-indigo-400" />
                            <span className="max-w-[120px] truncate">{src.metadata?.filename || "Source File"}</span>
                          </button>
                        );
                      })}
                    </div>

                    {/* Monospace Inline Collapsible Snippet preview */}
                    {expandedSourceIdx !== null && msg.sources.some(src => (src.citation_idx || (msg.sources?.indexOf(src) ?? 0) + 1) === expandedSourceIdx) && (
                      <div className="mt-3 bg-slate-950/60 border border-slate-800/80 rounded-xl overflow-hidden animate-in fade-in slide-in-from-top-1 duration-200">
                        {msg.sources.map((src, idx) => {
                          const citIdx = src.citation_idx || (idx + 1);
                          if (expandedSourceIdx !== citIdx) return null;
                          return (
                            <div key={idx} id={`source-${citIdx}`} className="p-3.5">
                              <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-800/50">
                                <div className="flex items-center gap-2 text-xs font-semibold text-slate-350">
                                  <span className="w-5 h-5 rounded bg-indigo-500/25 flex items-center justify-center text-[10px] font-bold text-indigo-400 border border-indigo-500/30">
                                    {citIdx}
                                  </span>
                                  <span className="truncate max-w-[200px] sm:max-w-[350px]">{src.metadata?.filename || "Unknown Source"}</span>
                                  <span className="text-[10px] text-slate-500 font-normal font-mono">chunk_id: {src.id || "N/A"}</span>
                                </div>
                                <button 
                                  onClick={() => setExpandedSourceIdx(null)}
                                  className="text-[10px] font-medium text-indigo-400 hover:text-indigo-300 hover:underline transition-colors"
                                >
                                  Close Snippet
                                </button>
                              </div>
                              <div className="text-xs text-slate-450 leading-relaxed font-mono whitespace-pre-wrap max-h-[160px] overflow-y-auto scrollbar-thin pr-1 select-text bg-slate-950/40 p-2.5 rounded-lg border border-slate-900">
                                {src.text || "No text chunk preview available."}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center shrink-0">
                  <User className="w-5 h-5 text-slate-300" />
                </div>
              )}
            </div>
          ))}

          {/* Pulse Shimmer Chat Loading State */}
          {isLoading && messages[messages.length - 1]?.role === "user" && (
            <div className="flex gap-4 justify-start animate-pulse">
              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-slate-700">
                <Bot className="w-5 h-5 text-slate-500" />
              </div>
              <div className="p-5 rounded-2xl rounded-bl-none max-w-[85%] bg-slate-800 border border-white/5 shadow-xl flex flex-col gap-3.5 w-[350px]">
                <div className="h-3.5 bg-slate-700/50 rounded-full w-3/4"></div>
                <div className="h-3.5 bg-slate-700/50 rounded-full w-5/6"></div>
                <div className="h-3.5 bg-slate-700/50 rounded-full w-1/2"></div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="absolute bottom-0 w-full bg-gradient-to-t from-slate-900 via-slate-900 to-transparent pt-10 pb-6 px-4">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="relative rounded-2xl bg-slate-800 shadow-2xl border border-slate-700 focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/50 transition-all">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about your documents..."
              className="w-full bg-transparent p-4 pr-14 outline-none text-slate-200 placeholder:text-slate-500 h-[60px]"
            />
            <button 
              type="submit" 
              disabled={isLoading || !input.trim()}
              className="absolute right-2 top-2 p-2.5 bg-indigo-500 hover:bg-indigo-600 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl transition-colors h-[44px] w-[44px] flex items-center justify-center"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </form>
          <div className="text-center mt-2 text-xs text-slate-500">
            AI can make mistakes. Verify important information using the cited sources.
          </div>
        </div>
      </div>
    </div>
  );
}
