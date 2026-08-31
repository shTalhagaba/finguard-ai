"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <main className="max-w-xl rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/30">
          <p className="text-sm uppercase tracking-[0.35em] text-cyan-300">FinGuard AI</p>
          <h1 className="mt-4 text-3xl font-semibold">Something went wrong</h1>
          <p className="mt-3 text-slate-300">
            The app hit an unexpected error. You can retry the request, or reload the page if the
            issue keeps happening.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-6 rounded-full bg-cyan-400 px-5 py-3 font-medium text-slate-950 transition hover:bg-cyan-300"
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
