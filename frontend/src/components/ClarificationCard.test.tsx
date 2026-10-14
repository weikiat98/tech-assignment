import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ClarificationCard from "./ClarificationCard";
import { ToastProvider } from "./ui";

describe("ClarificationCard", () => {
  it("is a named region that takes focus, described by the question rather than read out as an alert", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <ClarificationCard runId="r1" question="Which sector do you mean?" suggestions={["Technology"]} onAnswered={() => {}} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    const region = screen.getByRole("region", { name: "The coordinator needs a clarification" });
    expect(region).toHaveAccessibleDescription("Which sector do you mean?");
    expect(region).toHaveFocus();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Technology" })).toBeInTheDocument();
  });
});
