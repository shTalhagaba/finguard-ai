"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type ChatRole = "user" | "assistant";

type Source = {
  filename: string;
  chunk_index: number;
};

type Message = {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Source[];
};

type UploadResponse = {
  message: string;
  filename: string;
  stored_as: string;
  characters_extracted: number;
  chunks_created: number;
  chunks_stored: number;
  preview: string;
};

type ChatResponse = {
  answer: string;
  sources?: Source[];
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function createId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M7 3.75A2.75 2.75 0 0 1 9.75 1h4.69c.73 0 1.43.29 1.95.81l2.8 2.8c.52.52.81 1.22.81 1.95v10.69A2.75 2.75 0 0 1 17.25 20.0H9.75A2.75 2.75 0 0 1 7 17.25V3.75Z"
        fill="currentColor"
        opacity=".18"
      />
      <path
        d="M13.5 1.75V5a1 1 0 0 0 1 1h3.25"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9 11.25h6M9 14.75h6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="m12 2 1.7 5.8L20 9.5l-5.3 1.7L12 17l-2.7-5.8L4 9.5l6.3-1.7L12 2Z"
        fill="currentColor"
      />
      <path
        d="m5 15 .8 2.5L8 18.3l-2.2.8L5 21l-.8-1.9L2 18.3l2.2-.8L5 15Z"
        fill="currentColor"
        opacity=".75"
      />
    </svg>
  );
}

function UploadWave({ active }: { active: boolean }) {
  return (
    <div className="flex items-end gap-1">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className={`h-2 w-2 rounded-full bg-emerald-300 transition-all ${
            active ? "animate-pulse" : "opacity-40"
          }`}
          style={{ animationDelay: `${index * 120}ms` }}
        />
      ))}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
        <SparkIcon />
      </span>
      <span className="inline-flex items-center gap-1.5 text-sm text-slate-300">
        <span>FinGuard AI is analyzing</span>
        <span className="flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-300" />
        </span>
      </span>
    </div>
  );
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [documentReady, setDocumentReady] = useState(false);
  const [documentStatus, setDocumentStatus] = useState<string>(
    "Waiting for a PDF upload"
  );
  const [documentMetrics, setDocumentMetrics] = useState<UploadResponse | null>(
    null
  );
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const filePickerId = useMemo(() => `pdf-${createId("picker")}`, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const selectedFileName = file?.name ?? "No document selected";
  const documentCount = documentReady ? 1 : 0;

  const resetDocument = () => {
    setFile(null);
    setDocumentReady(false);
    setDocumentMetrics(null);
    setDocumentStatus("Waiting for a PDF upload");
    setUploadError(null);
    setChatError(null);
    setMessages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const chooseFile = (pickedFile: File | null) => {
    if (!pickedFile) return;

    if (!pickedFile.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Please choose a PDF file.");
      return;
    }

    setFile(pickedFile);
    setDocumentReady(false);
    setDocumentMetrics(null);
    setDocumentStatus("PDF selected. Ready to process.");
    setUploadError(null);
    setChatError(null);
  };

  const uploadDocument = async () => {
    if (!file || uploading) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setChatError(null);
    setDocumentStatus("Uploading and processing document...");

    const timer = window.setInterval(() => {
      setUploadProgress((current) => Math.min(current + 7, 92));
    }, 180);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const data = (await response.json()) as UploadResponse & {
        detail?: string;
      };

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }

      setUploadProgress(100);
      setDocumentMetrics(data);
      setDocumentReady(true);
      setDocumentStatus("Document indexed and ready for chat.");
      setMessages([
        {
          id: createId("assistant"),
          role: "assistant",
          content: `Document "${data.filename}" has been processed successfully. You can now ask questions about it.`,
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Something went wrong while uploading.";

      setUploadError(message);
      setDocumentStatus("Upload failed. Try another PDF.");
      setDocumentReady(false);
    } finally {
      window.clearInterval(timer);
      setUploading(false);
    }
  };

  const askQuestion = async () => {
    if (!documentReady || !question.trim() || loading) return;

    const currentQuestion = question.trim();
    setQuestion("");
    setChatError(null);
    setMessages((prev) => [
      ...prev,
      { id: createId("user"), role: "user", content: currentQuestion },
    ]);
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: currentQuestion,
        }),
      });

      const data = (await response.json()) as ChatResponse & {
        detail?: string;
      };

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
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Something went wrong.";
      setChatError(message);
      setMessages((prev) => [
        ...prev,
        {
          id: createId("assistant"),
          role: "assistant",
          content: message,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.16),_transparent_34%),linear-gradient(180deg,#020617_0%,#07111f_52%,#04070d_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-4 rounded-3xl border border-white/10 bg-white/5 px-5 py-4 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-400/25 bg-cyan-400/10 text-cyan-200 shadow-lg shadow-cyan-500/10">
                <DocumentIcon />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/70">
                  FinGuard AI
                </p>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                  Premium document intelligence dashboard
                </h1>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-200">
                API connected
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">
                {API_URL}
              </div>
            </div>
          </div>
        </header>

        <div className="grid flex-1 gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="rounded-3xl border border-white/10 bg-slate-950/70 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl sm:p-5">
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      Upload Document
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Drag and drop a PDF or choose one from your device.
                    </p>
                  </div>
                  <UploadWave active={uploading} />
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
                    chooseFile(e.dataTransfer.files?.[0] ?? null);
                  }}
                  htmlFor={filePickerId}
                  className={`mt-4 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-4 py-6 text-center transition ${
                    isDragging
                      ? "border-cyan-300 bg-cyan-400/10"
                      : "border-white/15 bg-black/20 hover:border-cyan-300/50 hover:bg-white/5"
                  }`}
                >
                  <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-200">
                    <SparkIcon />
                  </div>
                  <p className="text-sm font-medium text-white">
                    {file ? file.name : "Drop your PDF here"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    PDF only, processed through your FastAPI RAG pipeline
                  </p>
                </label>

                <input
                  ref={fileInputRef}
                  id={filePickerId}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
                />

                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex flex-1 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white transition hover:bg-white/10"
                  >
                    Choose PDF
                  </button>
                  <button
                    type="button"
                    onClick={uploadDocument}
                    disabled={!file || uploading}
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
                      style={{ width: `${uploading ? uploadProgress : documentReady ? 100 : 0}%` }}
                    />
                  </div>
                </div>

                {uploadError ? (
                  <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-100">
                    {uploadError}
                  </div>
                ) : null}
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Selected Document
                  </p>
                  <p className="mt-2 break-words text-sm font-medium text-white">
                    {selectedFileName}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    {documentReady ? "Ready for chat" : "Not processed yet"}
                  </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Processing Status
                  </p>
                  <p className="mt-2 text-sm font-medium text-white">
                    {documentStatus}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    {documentReady
                      ? "Conversation unlocked"
                      : "Chat remains locked until indexing is complete"}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Documents
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {documentCount}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Chunks
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatNumber(documentMetrics?.chunks_stored ?? 0)}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    System Status
                  </p>
                  <p className="mt-2 text-sm font-medium text-white">
                    {documentReady ? "Operational" : "Awaiting upload"}
                  </p>
                </div>
              </div>

              {documentMetrics ? (
                <div className="rounded-2xl border border-cyan-400/15 bg-cyan-400/5 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/70">
                    Document Metrics
                  </p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Characters</p>
                      <p className="mt-1 text-sm font-medium text-white">
                        {formatNumber(documentMetrics.characters_extracted)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Chunks Created</p>
                      <p className="mt-1 text-sm font-medium text-white">
                        {formatNumber(documentMetrics.chunks_created)}
                      </p>
                    </div>
                  </div>
                  <p className="mt-4 text-xs text-slate-400">
                    {documentMetrics.preview
                      ? `Preview: ${documentMetrics.preview.slice(0, 120)}${
                          documentMetrics.preview.length > 120 ? "..." : ""
                        }`
                      : "Preview unavailable."}
                  </p>
                </div>
              ) : null}

              <button
                type="button"
                onClick={resetDocument}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-200 transition hover:bg-white/10"
              >
                Reset workspace
              </button>
            </div>
          </aside>

          <section className="flex min-h-[72vh] flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950/70 shadow-2xl shadow-black/20 backdrop-blur-xl">
            <div className="border-b border-white/10 px-4 py-4 sm:px-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/70">
                    Chat Workspace
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Document Q&A with source citations
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Ask follow-up questions once the PDF is indexed. Responses
                    include backend-provided sources when available.
                  </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        documentReady ? "bg-emerald-400" : "bg-amber-400"
                      }`}
                    />
                    <span>{documentReady ? "Ready" : "Locked until upload"}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
              {messages.length === 0 ? (
                <div className="flex min-h-[54vh] flex-col items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/[0.03] px-6 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                    <SparkIcon />
                  </div>
                  <h3 className="mt-5 text-xl font-semibold text-white">
                    Your conversation will appear here
                  </h3>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
                    Upload a PDF from the sidebar to unlock the chat. Once the
                    backend finishes processing, you can ask about figures,
                    clauses, summaries, and key insights.
                  </p>
                  <div className="mt-6 grid gap-3 text-left sm:grid-cols-3">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-medium text-white">
                        Fast upload flow
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        Drag, drop, and process PDFs directly from the browser.
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-medium text-white">
                        Source-aware answers
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        Assistant responses display source chunks from the RAG
                        backend.
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-medium text-white">
                        Locked until ready
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        Prevents queries before document indexing completes.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-5">
                  {messages.map((message) => {
                    const isUser = message.role === "user";

                    return (
                      <div
                        key={message.id}
                        className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-[92%] rounded-[1.5rem] border px-4 py-3 shadow-lg sm:max-w-[80%] sm:px-5 ${
                            isUser
                              ? "border-cyan-400/20 bg-gradient-to-br from-cyan-400 to-emerald-300 text-slate-950"
                              : "border-white/10 bg-white/5 text-slate-100"
                          }`}
                        >
                          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] opacity-70">
                            <span>{isUser ? "You" : "FinGuard AI"}</span>
                          </div>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 sm:text-[15px]">
                            {message.content}
                          </p>

                          {message.sources?.length ? (
                            <div className="mt-4 border-t border-white/10 pt-3">
                              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                                Sources
                              </p>
                              <div className="mt-2 space-y-2">
                                {message.sources.map((source, index) => (
                                  <div
                                    key={`${source.filename}-${source.chunk_index}-${index}`}
                                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300"
                                  >
                                    <span className="font-medium text-white">
                                      {source.filename}
                                    </span>
                                    <span className="text-slate-500">
                                      {" "}
                                      · Chunk {source.chunk_index}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}

                  {loading ? (
                    <div className="flex justify-start">
                      <div className="max-w-[92%] rounded-[1.5rem] border border-white/10 bg-white/5 px-4 py-4 shadow-lg sm:max-w-[80%] sm:px-5">
                        <TypingIndicator />
                      </div>
                    </div>
                  ) : null}

                  <div ref={chatEndRef} />
                </div>
              )}
            </div>

            <div className="border-t border-white/10 p-4 sm:p-6">
              {chatError ? (
                <div className="mb-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                  {chatError}
                </div>
              ) : null}

              <div className="rounded-[1.5rem] border border-white/10 bg-black/30 p-3 shadow-inner shadow-black/20">
                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                  <div className="flex-1">
                    <label className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                      Ask a question
                    </label>
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
                      disabled={!documentReady || loading}
                      placeholder={
                        documentReady
                          ? "Ask about clauses, numbers, summaries, risks, or specific sections..."
                          : "Upload and process a PDF first"
                      }
                      className="w-full resize-none rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-300/40 disabled:cursor-not-allowed disabled:opacity-50"
                    />
                  </div>

                  <div className="flex gap-3 md:flex-col">
                    <button
                      type="button"
                      onClick={uploadDocument}
                      disabled={!file || uploading}
                      className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40 md:w-36"
                    >
                      {uploading ? "Working..." : "Reprocess"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void askQuestion()}
                      disabled={!documentReady || !question.trim() || loading}
                      className="rounded-2xl bg-gradient-to-r from-cyan-400 to-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 md:w-36"
                    >
                      {loading ? "Sending..." : "Send"}
                    </button>
                  </div>
                </div>

                <div className="mt-3 flex flex-col gap-2 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
                  <span>Press Enter to send, Shift+Enter for a new line.</span>
                  <span>
                    {documentReady
                      ? "Chat is enabled"
                      : "Chat is disabled until processing finishes"}
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
