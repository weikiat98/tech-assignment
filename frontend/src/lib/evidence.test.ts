import { describe, expect, it } from "vitest";
import { markCitedNumbers } from "./evidence";
import type { Fact } from "./types";

const fact = (display: string): Fact => ({
  id: "F1",
  key: "k",
  label: "l",
  value: 0,
  unit: "",
  display,
  method: "level",
  params: {},
  source_keys: [],
  derived: false,
});

const cited = (text: string, facts: Fact[]) =>
  markCitedNumbers(text, facts)
    .filter((s) => s.cited)
    .map((s) => s.text);

describe("evidence mark", () => {
  it("marks a cited display value and keeps the full text", () => {
    const text = "Employment rose from 118,300 in 2020 to 141,900 in 2024.";
    const segs = markCitedNumbers(text, [fact("118,300"), fact("141,900")]);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs.filter((s) => s.cited).map((s) => s.text)).toEqual(["118,300", "141,900"]);
  });

  it("matches the bare number of a display with a unit", () => {
    expect(cited("about 3.4 thousand more jobs", [fact("3.4 thousand")])).toEqual(["3.4 thousand"]);
    expect(cited("a rise of 20.0% overall", [fact("20.0%")])).toEqual(["20.0%"]);
  });

  it("never marks part of a longer number, or a year", () => {
    expect(cited("141,9000 and 2141,900", [fact("141,900")])).toEqual([]);
    expect(cited("in 2020 it was 20", [fact("20")])).toEqual(["20"]);
  });

  it("marks a fall written without the minus sign", () => {
    expect(cited("vacancies fell 3.2% in 2023", [fact("-3.2%")])).toEqual(["3.2%"]);
  });

  it("leaves text unmarked without cited facts", () => {
    expect(markCitedNumbers("No numbers cited.", [undefined])).toEqual([{ text: "No numbers cited.", cited: false }]);
  });
});
