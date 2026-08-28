"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";

type DocumentStatus =
  | "processing"
  | "completed"
  | "failed"
  | "duplicate"
  | string;

type DocumentRecord = {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  error: string | null;
  characters_extracted: number;
  chunks_created: number;
  chunks_stored: number;
  preview: string;
};

type UploadResponse = {
  documents: Array<DocumentRecord & { message?: string; detail?: string }>;
  failures: Array<{ filename: string; detail: string; document_id?: string }>;
};

type Source = {
  document?: string;
  page?: number | null;
  chunk?: {
    index?: number | null;
  };
  excerpt?: string | null;
  document_id?: string;
  stored_as?: string;
  relevance_score?: number;
  rank_score?: number;
};

type ChatResponse = {
  answer: string;
  sources?: Source[];
  contextualized_query?: string;
  task?: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  contextualizedQuery?: string;
  task?: string;
};

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

type AuthState = {
  accessToken: string;
  user: {
    id: string;
    email: string;
    display_name: string;
  };
};

type AuthResponsePayload = {
  access_token: string;
  token_type: string;
  user: AuthState["user"];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const MAX_HISTORY_TURNS = 8;
const MAX_HISTORY_CHARS = 1600;

function createId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function timeLabel(value: string) {
  return new Date(value).toLocaleString();
}

function statusStyle(status: string) {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-200";
    case "processing":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-200";
    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-200";
    case "duplicate":
      return "border-amber-400/20 bg-amber-400/10 text-amber-200";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function buildChatHistory(messages: Message[]): ChatTurn[] {
  const recentMessages = messages.slice(-MAX_HISTORY_TURNS * 2);
  const turns: ChatTurn[] = [];
  let totalChars = 0;

  for (const message of recentMessages) {
    if (message.role === "user" || message.role === "assistant") {
      const content = message.content.replace(/\s+/g, " ").trim();
      if (!content) continue;
      const nextChars = content.length + message.role.length + 2;
      if (turns.length >= MAX_HISTORY_TURNS || totalChars + nextChars > MAX_HISTORY_CHARS) {
        break;
      }
      turns.push({ role: message.role, content });
      totalChars += nextChars;
    }
  }

  return turns;
}

export default function Home() {
  const [auth, setAuth] = useState<AuthState | null>(() => {
    if (typeof window === "undefined") return null;
    const saved = window.localStorage.getItem("finguard-auth");
    if (!saved) return null;
    try {
      return JSON.parse(saved) as AuthState;
    } catch {
      window.localStorage.removeItem("finguard-auth");
      return null;
    }
  });
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const exampleQuestions = [
    "What are the KYC requirements?",
    "What is the international transfer limit?",
    "Compare domestic and international transfer limits.",
    "What is the refund period?",
    "Which transactions can trigger fraud monitoring?",
    "Summarize the AML policy.",
  ];

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const filePickerId = useMemo(() => `pdf-${createId("picker")}`, []);
  const authHeaders = useMemo(
    () =>
      auth
        ? {
            Authorization: `Bearer ${auth.accessToken}`,
          }
        : {},
    [auth]
  );

  useEffect(() => {
    if (!auth) return;
    window.localStorage.setItem("finguard-auth", JSON.stringify(auth));
  }, [auth]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    if (!auth) return;
    const loadDocuments = async () => {
      setDocumentsLoading(true);
      setDocumentError(null);
      try {
        const response = await fetch(`${API_URL}/api/documents`, { headers: authHeaders });
        const data = (await response.json()) as { documents?: DocumentRecord[]; detail?: string };
        if (!response.ok) {
          throw new Error(data.detail || "Failed to load documents.");
        }
        const nextDocuments = data.documents ?? [];
        setDocuments(nextDocuments);
        setActiveDocumentId((current) => {
          if (current && nextDocuments.some((doc) => doc.document_id === current)) {
            return current;
          }
          return nextDocuments[0]?.document_id ?? null;
        });
      } catch (error) {
        setDocumentError(error instanceof Error ? error.message : "Failed to load documents.");
      } finally {
        setDocumentsLoading(false);
      }
    };

    void loadDocuments();
  }, [auth, authHeaders]);

  const readyDocuments = documents.filter((document) => document.status === "completed");
  const selectedDocument = documents.find((document) => document.document_id === activeDocumentId) ?? null;

  const totalChunks = documents.reduce((sum, document) => sum + document.chunks_stored, 0);

  const refreshDocuments = async () => {
    const response = await fetch(`${API_URL}/api/documents`, { headers: authHeaders });
    const data = (await response.json()) as { documents?: DocumentRecord[]; detail?: string };
    if (!response.ok) {
      throw new Error(data.detail || "Failed to load documents.");
    }
    setDocuments(data.documents ?? []);
  };

  const chooseFiles = (pickedFiles: FileList | File[] | null) => {
    const nextFiles = Array.from(pickedFiles ?? []).filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );
    if (!nextFiles.length) {
      setUploadError("Please choose one or more PDF files.");
      return;
    }
    setFiles(nextFiles);
    setUploadError(null);
    setUploadNotice(null);
  };

  const uploadDocuments = async () => {
    if (!files.length || uploading) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setUploadNotice("Uploading and processing documents...");

    const timer = window.setInterval(() => {
      setUploadProgress((current) => Math.min(current + 6, 92));
    }, 180);

    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);
      }

      const response = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      const data = (await response.json()) as UploadResponse & { detail?: string };

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }

      setUploadProgress(100);
      await refreshDocuments();
      setFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      const successCount = data.documents?.length ?? 0;
      const failureCount = data.failures?.length ?? 0;
      setUploadNotice(
        failureCount
          ? `${successCount} document(s) indexed, ${failureCount} failed or were rejected.`
          : `${successCount} document(s) indexed successfully.`
      );
      setMessages((prev) => [
        ...prev,
        {
          id: createId("assistant"),
          role: "assistant",
          content:
            successCount > 0
              ? "Your documents are now indexed. Ask about KYC, AML, fraud, refunds, limits, fees, dates, or policy comparisons, and I’ll stay grounded in the uploaded files."
              : "No documents were indexed.",
        },
      ]);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Something went wrong while uploading.");
      setUploadNotice("Upload failed. No new documents were indexed.");
    } finally {
      window.clearInterval(timer);
      setUploading(false);
    }
  };

  const deleteDocument = async (documentId: string) => {
    startTransition(async () => {
      try {
        const response = await fetch(`${API_URL}/api/documents/${documentId}`, {
          method: "DELETE",
          headers: authHeaders,
        });
        const data = (await response.json()) as { detail?: string };
        if (!response.ok) {
          throw new Error(data.detail || "Delete failed.");
        }
        await refreshDocuments();
        setActiveDocumentId((current) => (current === documentId ? null : current));
      } catch (error) {
        setDocumentError(error instanceof Error ? error.message : "Failed to delete document.");
      }
    });
  };

  const askQuestion = async () => {
    if (!question.trim() || loading) return;

    const currentQuestion = question.trim();
    setQuestion("");
    setChatError(null);
    setMessages((prev) => [
      ...prev,
      { id: createId("user"), role: "user", content: currentQuestion },
    ]);
    setLoading(true);

    try {
      const history = buildChatHistory(messages);
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({
          question: currentQuestion,
          top_k: 5,
          document_id: activeDocumentId || undefined,
          chat_history: history,
        }),
      });

      const data = (await response.json()) as ChatResponse & { detail?: string };

      if (!response.ok) {
        throw new Error(data.detail || "Failed to get response.");
      }

      setMessages((prev) => [
        ...prev,
        {
          id: createId("assistant"),
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          contextualizedQuery: data.contextualized_query,
          task: data.task,
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setChatError(message);
      setMessages((prev) => [
        ...prev,
        { id: createId("assistant"), role: "assistant", content: message },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.18),_transparent_35%),linear-gradient(180deg,#020617_0%,#07111f_52%,#04070d_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-4 rounded-3xl border border-white/10 bg-white/5 px-5 py-4 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/70">
                FinGuard AI
              </p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                Multi-document RAG workspace
              </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Upload multiple PDFs, inspect their status, delete stale content, and ask targeted FinTech policy questions from the uploaded corpus only.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {auth ? (
                <>
                  <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">
                    {auth.user.display_name}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setAuth(null);
                      window.localStorage.removeItem("finguard-auth");
                    }}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10"
                  >
                    Sign out
                  </button>
                </>
              ) : null}
              <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-200">
                API connected
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">
                {API_URL}
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">
                {documents.length} documents
              </div>
            </div>
          </div>
        </header>

        <div className="grid flex-1 gap-4 lg:grid-cols-[390px_minmax(0,1fr)]">
          <aside className="rounded-3xl border border-white/10 bg-slate-950/70 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl sm:p-5">
            <div className="space-y-4">
              {!auth ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm font-semibold text-white">Secure access</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Register or sign in to isolate documents, vectors, and chat history to your account.
                  </p>
                  <div className="mt-4 flex gap-2">
                    <button type="button" onClick={() => setAuthMode("login")} className={`rounded-full px-3 py-1 text-xs ${authMode === "login" ? "bg-cyan-400 text-slate-950" : "border border-white/10 bg-white/5 text-slate-300"}`}>Login</button>
                    <button type="button" onClick={() => setAuthMode("register")} className={`rounded-full px-3 py-1 text-xs ${authMode === "register" ? "bg-cyan-400 text-slate-950" : "border border-white/10 bg-white/5 text-slate-300"}`}>Register</button>
                  </div>
                  <div className="mt-3 space-y-2">
                    {authMode === "register" ? (
                      <input value={authName} onChange={(e) => setAuthName(e.target.value)} placeholder="Display name" className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none" />
                    ) : null}
                    <input value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} placeholder="Email" className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none" />
                    <input value={authPassword} onChange={(e) => setAuthPassword(e.target.value)} type="password" placeholder="Password" className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none" />
                    {authError ? <p className="text-xs text-rose-200">{authError}</p> : null}
                    <button
                      type="button"
                      disabled={authLoading}
                      onClick={async () => {
                        setAuthLoading(true);
                        setAuthError(null);
                        try {
                          const response = await fetch(`${API_URL}/api/auth/${authMode}`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(
                              authMode === "register"
                                ? { email: authEmail, password: authPassword, display_name: authName }
                                : { email: authEmail, password: authPassword }
                            ),
                          });
                          const data = (await response.json()) as AuthResponsePayload & { detail?: string };
                          if (!response.ok) throw new Error(data.detail || "Authentication failed.");
                          setAuth({ accessToken: data.access_token, user: data.user });
                        } catch (error) {
                          setAuthError(error instanceof Error ? error.message : "Authentication failed.");
                        } finally {
                          setAuthLoading(false);
                        }
                      }}
                      className="w-full rounded-xl bg-gradient-to-r from-cyan-400 to-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950"
                    >
                      {authLoading ? "Working..." : authMode === "register" ? "Create account" : "Sign in"}
                    </button>
                  </div>
                </div>
              ) : null}
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Upload PDFs</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Add one or many PDFs. Duplicate files are safely ignored by hash.
                    </p>
                  </div>
                  <div className="flex items-end gap-1">
                    {[0, 1, 2].map((index) => (
                      <span
                        key={index}
                        className={`h-2 w-2 rounded-full bg-emerald-300 transition-all ${
                          uploading ? "animate-pulse" : "opacity-40"
                        }`}
                        style={{ animationDelay: `${index * 120}ms` }}
                      />
                    ))}
                  </div>
                </div>

                <label
                  onDragEnter={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    setIsDragging(false);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    setIsDragging(false);
                    chooseFiles(e.dataTransfer.files);
                  }}
                  htmlFor={filePickerId}
                  className={`mt-4 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-4 py-6 text-center transition ${
                    isDragging
                      ? "border-cyan-300 bg-cyan-400/10"
                      : "border-white/15 bg-black/20 hover:border-cyan-300/50 hover:bg-white/5"
                  }`}
                >
                  <p className="text-sm font-medium text-white">
                    {files.length ? `${files.length} file(s) selected` : "Drop PDFs here"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Upload multiple files in one request
                  </p>
                </label>

                <input
                  ref={fileInputRef}
                  id={filePickerId}
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => chooseFiles(e.target.files)}
                />

                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex flex-1 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white transition hover:bg-white/10"
                  >
                    Choose PDFs
                  </button>
                  <button
                    type="button"
                    onClick={uploadDocuments}
                    disabled={!files.length || uploading}
                    className="inline-flex flex-1 items-center justify-center rounded-xl bg-gradient-to-r from-cyan-400 to-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {uploading ? "Processing..." : "Upload & Index"}
                  </button>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Processing progress</span>
                    <span>{uploading ? `${uploadProgress}%` : "Idle"}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-300"
                      style={{ width: `${uploading ? uploadProgress : 0}%` }}
                    />
                  </div>
                </div>

                {uploadError ? (
                  <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-100">
                    {uploadError}
                  </div>
                ) : null}
                {uploadNotice ? (
                  <div className="mt-4 rounded-2xl border border-cyan-400/15 bg-cyan-400/5 p-3 text-sm text-cyan-100">
                    {uploadNotice}
                  </div>
                ) : null}
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Documents</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(documents.length)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Ready</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(readyDocuments.length)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Chunks</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(totalChunks)}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Active Query Scope</p>
                <p className="mt-2 text-sm font-medium text-white">
                  {selectedDocument ? selectedDocument.filename : "All documents"}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  {selectedDocument
                    ? "Chat searches within this document only."
                    : "Chat searches across the full corpus."}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white">Uploaded Documents</p>
                  <button
                    type="button"
                    onClick={() => void refreshDocuments()}
                    className="text-xs text-cyan-200 hover:text-cyan-100"
                  >
                    Refresh
                  </button>
                </div>
                <div className="mt-3 space-y-3">
                  {documentError ? (
                    <p className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-100">
                      {documentError}
                    </p>
                  ) : null}
                  {documentsLoading ? (
                    <p className="text-sm text-slate-400">Loading documents...</p>
                  ) : documents.length === 0 ? (
                    <p className="text-sm text-slate-400">No documents uploaded yet.</p>
                  ) : (
                    documents.map((document) => (
                      <div
                        key={document.document_id}
                        className={`rounded-2xl border p-3 transition ${statusStyle(document.status)} ${
                          activeDocumentId === document.document_id ? "ring-1 ring-cyan-300/50" : ""
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() =>
                            setActiveDocumentId((current) =>
                              current === document.document_id ? null : document.document_id
                            )
                          }
                          className="w-full text-left"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium text-white">{document.filename}</p>
                              <p className="mt-1 text-xs text-slate-300">
                                {document.chunks_stored} chunks · {timeLabel(document.updated_at)}
                              </p>
                            </div>
                            <span className="rounded-full border px-2 py-1 text-[11px] font-medium uppercase tracking-[0.18em]">
                              {document.status}
                            </span>
                          </div>
                        </button>
                        {document.error ? (
                          <p className="mt-2 text-xs text-rose-100">{document.error}</p>
                        ) : null}
                        {document.preview ? (
                          <p className="mt-2 line-clamp-3 text-xs text-slate-300">{document.preview}</p>
                        ) : null}
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => setActiveDocumentId(document.document_id)}
                            className="text-xs text-cyan-200 hover:text-cyan-100"
                          >
                            Ask about this
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteDocument(document.document_id)}
                            disabled={isPending}
                            className="text-xs text-rose-200 hover:text-rose-100 disabled:opacity-40"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </aside>

          <section className="flex min-h-[72vh] flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950/70 shadow-2xl shadow-black/20 backdrop-blur-xl">
            <div className="border-b border-white/10 px-4 py-4 sm:px-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/70">
                    Retrieval chat
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Search across all uploaded documents
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Every answer shows only retrieved document citations, with page and chunk details when available.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                  {selectedDocument ? `Scoped to ${selectedDocument.filename}` : "Scoped to the full corpus"}
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[360px] items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/5 p-8 text-center">
                  <div className="max-w-lg">
                    <p className="text-lg font-semibold text-white">Ask a question once your PDFs are indexed.</p>
                    <p className="mt-2 text-sm leading-6 text-slate-400">
                      Try asking for KYC requirements, AML controls, fraud triggers, refund periods, limits, fees, dates, comparisons, or plain-language summaries.
                    </p>
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                      {exampleQuestions.map((example) => (
                        <button
                          key={example}
                          type="button"
                          onClick={() => setQuestion(example)}
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-400/10 hover:text-white"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[92%] rounded-3xl border px-4 py-3 shadow-lg sm:max-w-[80%] ${
                          message.role === "user"
                            ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-50"
                            : "border-white/10 bg-white/5 text-slate-100"
                        }`}
                      >
                        {message.role === "assistant" && (message.contextualizedQuery || message.task) ? (
                          <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-cyan-200/70">
                            {message.task ? `Task: ${message.task.replace(/_/g, " ")}` : "Retrieved answer"}
                          </p>
                        ) : null}
                        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                        {message.sources?.length ? (
                          <div className="mt-3 border-t border-white/10 pt-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Sources</p>
                            <div className="mt-2 space-y-2">
                              {message.sources.map((source, index) => {
                                const chunkIndex = source.chunk?.index;
                                const sourceLabel = source.document ?? "Unknown document";
                                const pageLabel = source.page != null ? `Page ${source.page}` : "Page unavailable";
                                const chunkLabel = chunkIndex != null ? `Chunk ${chunkIndex}` : "Chunk unavailable";

                                return (
                                  <details
                                    key={`${source.document_id ?? "source"}-${index}`}
                                    className="group rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300 transition open:bg-black/30"
                                  >
                                    <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                                      <div>
                                        <p className="font-medium text-white">{sourceLabel}</p>
                                        <p className="mt-1 text-slate-400">
                                          {pageLabel} · {chunkLabel}
                                        </p>
                                      </div>
                                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-400 transition group-open:text-cyan-200">
                                        Details
                                      </span>
                                    </summary>
                                    <div className="mt-3 space-y-2 border-t border-white/10 pt-3">
                                      {source.excerpt ? (
                                        <p className="leading-5 text-slate-300">
                                          {source.excerpt}
                                        </p>
                                      ) : (
                                        <p className="leading-5 text-slate-500">
                                          No excerpt available for this source.
                                        </p>
                                      )}
                                      <div className="flex flex-wrap gap-2 text-[11px] text-slate-400">
                                        {source.document_id ? (
                                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                                            {source.document_id}
                                          </span>
                                        ) : null}
                                        {source.relevance_score != null ? (
                                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                                            Relevance {source.relevance_score}
                                          </span>
                                        ) : null}
                                      </div>
                                    </div>
                                  </details>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>

            <div className="border-t border-white/10 p-4 sm:p-6">
              <div className="space-y-3">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void askQuestion();
                    }
                  }}
                  rows={3}
                  placeholder="Ask about KYC, AML, fraud, refunds, limits, fees, dates, or policy comparisons..."
                  className="w-full resize-none rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
                />
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-slate-400">
                    Enter sends, Shift+Enter adds a line break.
                  </p>
                  <button
                    type="button"
                    onClick={askQuestion}
                    disabled={!question.trim() || loading}
                    className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-cyan-400 to-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {loading ? "Searching..." : "Ask Gemini"}
                  </button>
                </div>
                {chatError ? (
                  <p className="text-sm text-rose-200">{chatError}</p>
                ) : null}
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
