import type { ChatSummary } from "./types";

export interface ChatGroup {
  label: "Pinned" | "Today" | "Previous 7 days" | "Older";
  chats: ChatSummary[];
}

const DAY = 86_400_000;

/**
 * Sidebar groups: Pinned, then by the day of the last activity. "Today" is the calendar day in the viewer's
 * time zone, so it needs the API's UTC timestamps to carry their offset (todo.md R10).
 */
export function groupChats(chats: ChatSummary[], now: Date = new Date()): ChatGroup[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const groups: ChatGroup[] = [
    { label: "Pinned", chats: [] },
    { label: "Today", chats: [] },
    { label: "Previous 7 days", chats: [] },
    { label: "Older", chats: [] },
  ];
  const byRecent = [...chats].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  for (const c of byRecent) {
    const t = Date.parse(c.updated_at);
    const g = c.pinned ? 0 : t >= startOfToday ? 1 : t >= startOfToday - 7 * DAY ? 2 : 3;
    groups[g].chats.push(c);
  }
  return groups.filter((g) => g.chats.length > 0);
}

/** The question that stays selectable even when copying a whole answer: plain text of a finished answer. */
export function answerText(summary: string, findings: string[]): string {
  return [summary, ...findings.map((f) => `- ${f}`)].filter(Boolean).join("\n");
}
