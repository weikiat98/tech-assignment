import { describe, expect, it } from "vitest";
import { answerText, groupChats } from "./chats";
import type { ChatSummary } from "./types";

const NOW = new Date(2026, 9, 14, 15, 0, 0); // 14 Oct 2026, 15:00 local
const chat = (id: string, daysAgo: number, pinned = false, hour = 9): ChatSummary => ({
  id,
  title: id,
  pinned,
  created_at: "",
  updated_at: new Date(2026, 9, 14 - daysAgo, hour).toISOString(),
  status: "completed",
  turns: 1,
});

describe("groupChats", () => {
  it("groups by day of last activity, pinned first, newest first inside a group", () => {
    const groups = groupChats(
      [chat("old", 30), chat("week", 3), chat("today-early", 0, false, 8), chat("pin", 20, true), chat("today-late", 0, false, 14)],
      NOW,
    );
    expect(groups.map((g) => g.label)).toEqual(["Pinned", "Today", "Previous 7 days", "Older"]);
    expect(groups[1].chats.map((c) => c.id)).toEqual(["today-late", "today-early"]);
    expect(groups[0].chats.map((c) => c.id)).toEqual(["pin"]);
  });

  it("leaves out empty groups and treats yesterday evening as the previous 7 days, not today", () => {
    expect(groupChats([], NOW)).toEqual([]);
    const groups = groupChats([chat("yesterday", 1, false, 23)], NOW);
    expect(groups.map((g) => g.label)).toEqual(["Previous 7 days"]);
  });
});

describe("answerText", () => {
  it("copies the summary and findings as plain text", () => {
    expect(answerText("Summary.", ["One.", "Two."])).toBe("Summary.\n- One.\n- Two.");
    expect(answerText("", [])).toBe("");
  });
});
