import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import ChatBar from "./ChatBar";
import Sidebar from "./Sidebar";
import Turn from "./Turn";
import { ToastProvider, TooltipProvider } from "./ui";
import { api } from "../lib/api";
import type { ChatSummary, ChatTurn } from "../lib/types";

vi.mock("../lib/useRunEvents", () => ({ useRunEvents: () => ({ events: [], connected: false, liveAfter: 0 }) }));

const chat = (id: string, title: string, pinned = false): ChatSummary => ({
  id,
  title,
  pinned,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  status: "completed",
  turns: 1,
});

function wrap(ui: ReactNode, route = "/") {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());

describe("Sidebar", () => {
  it("groups pinned chats first and renames in place", async () => {
    vi.spyOn(api, "listChats").mockResolvedValue([chat("a", "Tech jobs"), chat("b", "Retrenchments", true)]);
    const rename = vi.spyOn(api, "renameChat").mockResolvedValue(chat("a", "Tech workforce"));
    const user = userEvent.setup();
    wrap(<Sidebar />);
    await screen.findByRole("link", { name: /Tech jobs/ });
    const groups = screen.getAllByRole("region").map((g) => g.getAttribute("aria-label")).filter((l) => l !== "Notifications (F8)");
    expect(groups).toEqual(["Pinned", "Today"]);

    await user.click(screen.getByRole("button", { name: "Actions for Tech jobs" }));
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const field = screen.getByRole("textbox", { name: "Chat title" });
    await user.clear(field);
    await user.type(field, "Tech workforce{Enter}");
    await waitFor(() => expect(rename).toHaveBeenCalledWith("a", "Tech workforce"));
  });

  it("asks before deleting, and Esc does not delete", async () => {
    vi.spyOn(api, "listChats").mockResolvedValue([chat("a", "Tech jobs")]);
    const del = vi.spyOn(api, "deleteChat").mockResolvedValue(undefined);
    const user = userEvent.setup();
    wrap(<Sidebar />);
    await user.click(await screen.findByRole("button", { name: "Actions for Tech jobs" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete…" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Delete this chat?");
    await user.keyboard("{Escape}");
    expect(del).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Actions for Tech jobs" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete…" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("a"));
  });
});

describe("ChatBar", () => {
  const base = { value: "", onChange: () => {}, onSend: () => {}, placeholder: "Ask", options: { webContext: false, provider: "auto" as const }, onOptions: () => {} };

  it("sends on Enter, keeps Shift+Enter for a new line, and refuses very short questions", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<ChatBar {...base} value="ab" onSend={onSend} />);
    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    rerender(<ChatBar {...base} value="What about finance?" onSend={onSend} />);
    await user.type(screen.getByRole("textbox"), "{Shift>}{Enter}{/Shift}");
    expect(onSend).not.toHaveBeenCalled();
    await user.type(screen.getByRole("textbox"), "{Enter}");
    expect(onSend).toHaveBeenCalledOnce();
  });

  it("offers web context and model in the + menu", async () => {
    const onOptions = vi.fn();
    const user = userEvent.setup();
    render(<ChatBar {...base} onOptions={onOptions} />);
    await user.click(screen.getByRole("button", { name: "Options" }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "Include web context" }));
    expect(onOptions).toHaveBeenCalledWith({ webContext: true, provider: "auto" });
    await user.click(screen.getByRole("button", { name: "Options" }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Google Gemini" }));
    expect(onOptions).toHaveBeenLastCalledWith({ webContext: false, provider: "gemini" });
  });

  it("shows Stop instead of Send while a run is going", async () => {
    const onStop = vi.fn();
    render(<ChatBar {...base} busy onStop={onStop} disabled />);
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });
});

describe("Turn", () => {
  const version = (n: number) => ({ id: `run-${n}`, query: "What about finance?", status: "completed" as const, created_at: "", finished_at: "", total_cost_usd: 0, total_tokens: 0, chat_id: "c", turn: 2, version: n });
  const item: ChatTurn = { turn: 2, query: "What about finance?", versions: [version(1), version(2)] };
  const detail = (n: number) => ({
    ...version(n),
    options: {},
    intent: null,
    plan: null,
    error: null,
    result: {
      query: "q",
      intent: null,
      plan: null,
      report: { title: "T", executive_summary: `Summary of answer ${n}.`, key_findings: [{ text: `Finding ${n}.`, fact_ids: [], source_keys: [] }], sector_analysis: [], policy_implications: [], limitations: [] },
      verification: { passed: true, numeric_pass_rate: 1, citation_pass_rate: 1, entity_pass_rate: 1, attempt: 1, checks: [] },
      facts: [],
      charts: [],
      datasets: [],
      context_notes: [],
      warnings: [],
      fallbacks: [],
      llm_providers_used: [],
      total_tokens: 0,
      total_cost_usd: 0,
      trace_url: null,
      markdown: null,
      suggestions: ["What about technology?"],
    },
  });

  it("shows the newest answer, switches between versions, and previews a chosen tab", async () => {
    vi.spyOn(api, "getAnalysis").mockImplementation(async (id) => detail(id === "run-1" ? 1 : 2));
    const onPreview = vi.fn();
    const onFollowUp = vi.fn();
    const user = userEvent.setup();
    wrap(<Turn chatId="c" item={item} isLast previewRunId={null} onPreview={onPreview} onFollowUp={onFollowUp} onAnswered={() => {}} />);
    expect(await screen.findByText("Summary of answer 2.")).toBeInTheDocument();
    expect(screen.getByText("Answer 2 of 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Previous answer" }));
    expect(await screen.findByText("Summary of answer 1.")).toBeInTheDocument();
    expect(screen.getByText("Answer 1 of 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next answer" }));
    expect(await screen.findByText("Summary of answer 2.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(onPreview).toHaveBeenCalledWith("run-2", "Report");
    await user.click(screen.getByRole("button", { name: "Choose what to preview" }));
    await user.click(await screen.findByRole("menuitem", { name: "Charts" }));
    expect(onPreview).toHaveBeenLastCalledWith("run-2", "Charts");

    await user.click(screen.getByRole("button", { name: "What about technology?" }));
    expect(onFollowUp).toHaveBeenCalledWith("What about technology?");
  });

  it("asks the question again through the retry endpoint", async () => {
    vi.spyOn(api, "getAnalysis").mockResolvedValue(detail(2));
    const retry = vi.spyOn(api, "retryTurn").mockResolvedValue({} as never);
    const user = userEvent.setup();
    wrap(<Turn chatId="c" item={item} isLast={false} previewRunId={null} onPreview={() => {}} onFollowUp={() => {}} onAnswered={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledWith("c", 2);
    await waitFor(() => expect(screen.queryByRole("list", { name: "Follow-up questions" })).not.toBeInTheDocument());
  });
});
