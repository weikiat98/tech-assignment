import type { Fact } from "./types";

export interface Segment {
  text: string;
  /** True when this run of text is a number backed by one of the claim's cited facts. */
  cited: boolean;
}

const NUMBER = /-?\d[\d,]*(?:\.\d+)?%?/;

function escape(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split a claim into plain and cited segments for the evidence mark. A cited segment is a cited fact's
 * `display` string, or its bare number, standing as a whole number in the text (never part of a longer one).
 * Best effort: a number the writer phrased differently (e.g. "20%" for "20.0%") is simply left unmarked.
 */
export function markCitedNumbers(text: string, facts: (Fact | undefined)[]): Segment[] {
  const needles = new Set<string>();
  for (const f of facts) {
    if (!f?.display) continue;
    needles.add(f.display);
    const num = f.display.match(NUMBER)?.[0];
    if (num) {
      needles.add(num);
      if (num.startsWith("-")) needles.add(num.slice(1)); // "fell 3.2%" cites a -3.2% change
    }
  }
  const list = [...needles].filter((n) => /\d/.test(n)).sort((a, b) => b.length - a.length);
  if (!list.length) return [{ text, cited: false }];

  const pattern = new RegExp(`(?<![\\d.,])(?:${list.map(escape).join("|")})(?!\\d|[.,]\\d)`, "g");
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    const start = m.index ?? 0;
    if (start > last) out.push({ text: text.slice(last, start), cited: false });
    out.push({ text: m[0], cited: true });
    last = start + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), cited: false });
  return out.length ? out : [{ text, cited: false }];
}
