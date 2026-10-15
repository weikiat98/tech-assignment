import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RunActivity from "./RunActivity";
import { ToastProvider, TooltipProvider } from "../components/ui";
import { api } from "../lib/api";
import type { RunActivity as Activity, RunActivityBucket } from "../lib/types";

const counts = { completed: 0, failed: 0, cancelled: 0, active: 0, verified: 0, cost_usd: 0 };
const bucket = (start: string, label: string, runs: number, cumulative: number): RunActivityBucket => ({
  ...counts,
  start,
  label,
  from: `${start}T00:00:00+00:00`,
  to: `${start}T23:59:00+00:00`,
  runs,
  completed: runs,
  verified: runs,
  cumulative_runs: cumulative,
});

const activity = (period: Activity["period"], buckets: RunActivityBucket[]): Activity => ({
  period,
  tz: "UTC",
  totals: { ...counts, runs: 3, completed: 3, verified: 3, cost_usd: 0.02 },
  buckets,
});

beforeEach(() => vi.restoreAllMocks());

describe("RunActivity", () => {
  it("shows totals per period, lists a period's runs, and switches to months", async () => {
    const spy = vi.spyOn(api, "activity").mockImplementation(async (period) =>
      period === "week"
        ? activity("week", [bucket("2026-10-12", "Week of 12 Oct 2026", 2, 3), bucket("2026-10-05", "Week of 5 Oct 2026", 0, 1)])
        : activity("month", [bucket("2026-10-01", "October 2026", 3, 3)]),
    );
    const runs = vi.spyOn(api, "activityRuns").mockResolvedValue([
      { id: "r1", chat_id: "c1", query: "Tech jobs 2020-2024", status: "completed", created_at: "2026-10-13T02:00:00Z", seconds: 2, cost_usd: 0.01, verified: true },
    ]);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TooltipProvider>
          <ToastProvider>
            <MemoryRouter>
              <RunActivity />
            </MemoryRouter>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>,
    );

    const current = await screen.findByRole("row", { name: /Week of 12 Oct 2026/ });
    expect(within(current).getAllByRole("cell").at(-1)).toHaveTextContent("3");
    expect(await screen.findByRole("link", { name: "Tech jobs 2020-2024" })).toHaveAttribute("href", "/chats/c1");
    expect(runs).toHaveBeenCalledWith("2026-10-12T00:00:00+00:00", "2026-10-12T23:59:00+00:00");

    await user.click(screen.getByRole("button", { name: "Week of 5 Oct 2026" }));
    expect(await screen.findByText("No questions were asked in this period.")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Month" }));
    expect(await screen.findByRole("row", { name: /October 2026/ })).toBeInTheDocument();
    expect(spy).toHaveBeenLastCalledWith("month", expect.any(String));
  });
});
