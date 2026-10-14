import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRunEvents } from "./useRunEvents";

class FakeSocket {
  static last: FakeSocket;
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeSocket.last = this;
  }
  send(msg: object) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
  close() {}
}

const event = (seq: number) => ({ run_id: "r1", seq, agent: "system", type: "status", content: {}, tokens: 0, cost_usd: 0, ts: "" });

describe("useRunEvents", () => {
  beforeEach(() => vi.stubGlobal("WebSocket", FakeSocket));
  afterEach(() => vi.unstubAllGlobals());

  it("reports where the replayed history ends, from the server's marker, not the clock", () => {
    const { result } = renderHook(() => useRunEvents("r1", true));
    expect(result.current.liveAfter).toBeNull();
    act(() => {
      FakeSocket.last.send(event(1));
      FakeSocket.last.send(event(2));
      FakeSocket.last.send({ type: "replay_done", last_seq: 2 });
      FakeSocket.last.send(event(3));
    });
    expect(result.current.events.map((e) => e.seq)).toEqual([1, 2, 3]);
    expect(result.current.liveAfter).toBe(2);
  });

  it("keeps the first watermark when a reconnect replays missed events", () => {
    const { result } = renderHook(() => useRunEvents("r1", true));
    act(() => {
      FakeSocket.last.send({ type: "replay_done", last_seq: 0 });
      FakeSocket.last.send(event(1));
      FakeSocket.last.send({ type: "replay_done", last_seq: 1 }); // a later replay is not history
    });
    expect(result.current.liveAfter).toBe(0);
    expect(result.current.events).toHaveLength(1);
  });
});
