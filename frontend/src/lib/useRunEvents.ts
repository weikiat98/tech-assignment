import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";
import type { AgentEvent } from "./types";

/** Live agent events over WebSocket, with auto-reconnect and replay of missed events (?after=seq). */
export function useRunEvents(runId: string | undefined, active: boolean) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const lastSeq = useRef(0);

  useEffect(() => {
    setEvents([]);
    lastSeq.current = 0;
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    let attempts = 0;

    const connect = () => {
      socket = new WebSocket(wsUrl(runId, lastSeq.current));
      socket.onopen = () => {
        attempts = 0;
        setConnected(true);
      };
      socket.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.type === "ping" || typeof data.seq !== "number") return;
        if (data.seq <= lastSeq.current) return;
        lastSeq.current = data.seq;
        setEvents((prev) => [...prev, data as AgentEvent]);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed && active) {
          attempts += 1;
          retry = setTimeout(connect, Math.min(1000 * 2 ** attempts, 10000));
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, [runId, active]);

  return { events, connected };
}
