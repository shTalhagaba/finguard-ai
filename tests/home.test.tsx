import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../app/page";

const baseDocument = {
  document_id: "doc-1",
  filename: "policy.pdf",
  status: "completed",
  created_at: "2026-08-28T00:00:00Z",
  updated_at: "2026-08-28T00:00:00Z",
  error: null,
  characters_extracted: 1200,
  chunks_created: 3,
  chunks_stored: 3,
  preview: "Policy preview",
};

function mockJsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: async () => body,
  } as Response);
}

beforeEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("Home", () => {
  it("renders the empty state when no documents are available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockJsonResponse({ documents: [] })));
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);

    expect(await screen.findByText("No documents uploaded yet.")).toBeInTheDocument();
  });

  it("shows the loading state while documents are being fetched", async () => {
    let resolveFetch: (value: Response) => void = () => {};
    const pendingFetch = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });

    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingFetch));
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);
    expect(screen.getByText("Loading documents...")).toBeInTheDocument();

    await act(async () => {
      resolveFetch!(await mockJsonResponse({ documents: [] }));
    });
  });

  it("supports upload UI interactions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockJsonResponse({ documents: [] })));
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);
    expect(await screen.findByText("Upload PDFs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose PDFs" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload & Index" })).toBeDisabled();
  });

  it("shows API error state for failed uploads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/documents")) return mockJsonResponse({ documents: [] });
        if (url.includes("/api/upload")) return mockJsonResponse({ detail: "Upload failed." }, false, 400);
        return mockJsonResponse({});
      })
    );
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);

    await screen.findByText(/drop pdfs here/i);
    const file = new File(["pdf"], "policy.pdf", { type: "application/pdf" });

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/drop pdfs here/i, { selector: "input" }), {
        target: { files: [file] },
      });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Upload & Index" }));
    });

    await waitFor(() => {
      expect(screen.getByText("Upload failed.")).toBeInTheDocument();
    });
  });

  it("renders chat answers and sources", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/documents")) return mockJsonResponse({ documents: [baseDocument] });
        if (url.includes("/api/chat")) {
          return mockJsonResponse({
            answer: "The policy says identity verification is required.",
            sources: [
              {
                document: "policy.pdf",
                page: 2,
                chunk: { index: 0 },
                excerpt: "Identity verification is required.",
                document_id: "doc-1",
                relevance_score: 0.95,
              },
            ],
          });
        }
        return mockJsonResponse({});
      })
    );
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);

    const textarea = await screen.findByPlaceholderText(/ask about kyc/i);
    fireEvent.change(textarea, { target: { value: "What are the KYC requirements?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Gemini" }));

    expect(await screen.findByText("The policy says identity verification is required.")).toBeInTheDocument();
    expect((await screen.findAllByText("policy.pdf")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Page 2/)).toBeInTheDocument();
  });

  it("shows a chat error for unsupported questions or empty retrieval", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/documents")) return mockJsonResponse({ documents: [baseDocument] });
        if (url.includes("/api/chat")) return mockJsonResponse({ detail: "I couldn't find relevant information." }, false, 404);
        return mockJsonResponse({});
      })
    );
    window.localStorage.setItem(
      "finguard-auth",
      JSON.stringify({ accessToken: "token", user: { id: "u1", email: "user@example.com", display_name: "User" } })
    );

    render(<Home />);
    const textarea = await screen.findByPlaceholderText(/ask about kyc/i);
    fireEvent.change(textarea, { target: { value: "What is the moon policy?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Gemini" }));

    const matches = await screen.findAllByText("I couldn't find relevant information.");
    expect(matches.length).toBeGreaterThan(0);
  });
});
