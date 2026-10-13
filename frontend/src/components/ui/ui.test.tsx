import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ConfirmDialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Button,
  ScoreBar,
  StageProgress,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  ToastProvider,
  useToast,
} from "./index";

describe("Tabs", () => {
  it("moves selection with the arrow keys and exposes tab roles", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [v, setV] = useState("a");
      return (
        <Tabs value={v} onValueChange={setV}>
          <TabsList aria-label="results">
            <TabsTrigger value="a">Alpha</TabsTrigger>
            <TabsTrigger value="b">Beta</TabsTrigger>
            <TabsTrigger value="c">Gamma</TabsTrigger>
          </TabsList>
        </Tabs>
      );
    }
    render(<Harness />);
    expect(screen.getByRole("tablist", { name: "results" })).toBeInTheDocument();
    const alpha = screen.getByRole("tab", { name: "Alpha" });
    expect(alpha).toHaveAttribute("aria-selected", "true");
    alpha.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Beta" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Alpha" })).toHaveAttribute("aria-selected", "true"); // wraps
  });
});

describe("ConfirmDialog", () => {
  function Harness({ onConfirm }: { onConfirm: () => void }) {
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button onClick={() => setOpen(true)}>Delete item</Button>
        <ConfirmDialog open={open} onOpenChange={setOpen} title="Delete this?" description="Gone for good." onConfirm={onConfirm} />
      </>
    );
  }

  it("starts focus on Cancel and does not confirm on Esc", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Delete item" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this?" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("confirms only through the Delete button", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Delete item" }));
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("Switch", () => {
  it("toggles from its label and from the keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function Harness() {
      const [on, setOn] = useState(false);
      return (
        <Switch
          label="OpenAI down"
          checked={on}
          onCheckedChange={(c) => {
            onChange(c);
            setOn(c);
          }}
        />
      );
    }
    render(<Harness />);
    const sw = screen.getByRole("switch", { name: "OpenAI down" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    await user.click(screen.getByText("OpenAI down"));
    expect(sw).toHaveAttribute("aria-checked", "true");
    sw.focus();
    await user.keyboard(" ");
    expect(sw).toHaveAttribute("aria-checked", "false");
    expect(onChange.mock.calls.map((c) => c[0])).toEqual([true, false]);
  });
});

describe("DropdownMenu (export menu)", () => {
  it("opens from the keyboard and selects an item", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button>Export</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={() => onSelect("pdf")}>PDF report</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onSelect("md")}>Markdown</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    screen.getByRole("button", { name: "Export" }).focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("menu")).toBeInTheDocument();
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
  });

  it("renders link items with asChild (the export menu) without crashing", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button>Export</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem asChild onSelect={onSelect}>
            <a href="/api/v1/analyses/1/export?format=pdf">PDF report</a>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    await user.click(screen.getByRole("button", { name: "Export" }));
    const item = await screen.findByRole("menuitem", { name: "PDF report" });
    expect(item).toHaveAttribute("href", "/api/v1/analyses/1/export?format=pdf");
  });

  it("jumps to an item by typeahead", async () => {
    const user = userEvent.setup();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button>Export</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>PDF report</DropdownMenuItem>
          <DropdownMenuItem>Markdown</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    screen.getByRole("button", { name: "Export" }).focus();
    await user.keyboard("{Enter}");
    await screen.findByRole("menu");
    await user.keyboard("m");
    expect(screen.getByRole("menuitem", { name: "Markdown" })).toHaveFocus();
  });
});

describe("Progress", () => {
  it("exposes aria values for the quality score", () => {
    render(<ScoreBar score={0.82} />);
    const bar = screen.getByRole("progressbar", { name: "Data quality score" });
    expect(bar).toHaveAttribute("aria-valuenow", "82");
    expect(screen.getByText("0.82")).toBeInTheDocument();
  });

  it("is indeterminate while the run has no stage yet", () => {
    render(<StageProgress value={null} label="Analysis progress" />);
    expect(screen.getByRole("progressbar", { name: "Analysis progress" })).not.toHaveAttribute("aria-valuenow");
  });
});

describe("Toast", () => {
  it("announces a pushed toast and can dismiss it", async () => {
    const user = userEvent.setup();
    function Trigger() {
      const toast = useToast();
      return <Button onClick={() => toast({ title: "Could not cancel", description: "boom", tone: "error" })}>Go</Button>;
    }
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Go" }));
    expect(await screen.findByText("Could not cancel")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));
    await waitFor(() => expect(screen.queryByText("Could not cancel")).not.toBeInTheDocument());
  });
});
