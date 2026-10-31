import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { tokenStore } from "./api";

export type LiveMessage = { type: string; data: any };
type Listener = (m: LiveMessage) => void;

interface LiveState {
  status: "connecting" | "live" | "reconnecting";
  subscribe: (fn: Listener) => () => void;
}

const LiveCtx = createContext<LiveState | null>(null);
const PulseCtx = createContext<number[]>([]); // timestamps of recent events, drives the ward pulse line

export function LiveProvider({ children, enabled }: { children: ReactNode; enabled: boolean }) {
  const [status, setStatus] = useState<LiveState["status"]>("connecting");
  const [beats, setBeats] = useState<number[]>([]);
  const listeners = useRef(new Set<Listener>());

  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null;
    let retry = 1000;
    let closed = false;
    let ping: number | undefined;
    let timer: number | undefined;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws/monitoring?token=${encodeURIComponent(tokenStore.get() ?? "")}`);
      ws.onopen = () => {
        setStatus("live");
        retry = 1000;
        ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 20000);
      };
      ws.onmessage = (e) => {
        let msg: LiveMessage;
        try { msg = JSON.parse(e.data); } catch { return; }
        if (msg.type === "pong" || msg.type === "hello" || msg.type === "worker.heartbeat") {
          if (msg.type === "worker.heartbeat") listeners.current.forEach((fn) => fn(msg));
          return;
        }
        if (msg.type !== "monitoring.tracks" || (msg.data?.tracks?.length ?? 0) > 0) {
          const now = Date.now();
          setBeats((b) => [...b.filter((t) => now - t < 12000), now].slice(-40));
        }
        listeners.current.forEach((fn) => fn(msg));
      };
      ws.onclose = () => {
        window.clearInterval(ping);
        if (closed) return;
        setStatus("reconnecting");
        timer = window.setTimeout(connect, retry);
        retry = Math.min(retry * 2, 15000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      window.clearInterval(ping);
      window.clearTimeout(timer);
      ws?.close();
    };
  }, [enabled]);

  const subscribe = useCallback((fn: Listener) => {
    listeners.current.add(fn);
    return () => { listeners.current.delete(fn); };
  }, []);
  const value = useMemo(() => ({ status, subscribe }), [status, subscribe]);

  return (
    <LiveCtx.Provider value={value}>
      <PulseCtx.Provider value={beats}>{children}</PulseCtx.Provider>
    </LiveCtx.Provider>
  );
}

export function useLive() {
  const ctx = useContext(LiveCtx);
  if (!ctx) throw new Error("useLive outside LiveProvider");
  return ctx;
}

export const usePulse = () => useContext(PulseCtx);

/** Re-run `fn` whenever a live event whose type starts with one of `prefixes` arrives (throttled). */
export function useLiveRefresh(prefixes: string[], fn: () => void, throttleMs = 1200) {
  const { subscribe } = useLive();
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let last = 0;
    let pending: number | undefined;
    const unsub = subscribe((m) => {
      if (!prefixes.some((p) => m.type.startsWith(p))) return;
      const wait = Math.max(0, throttleMs - (Date.now() - last));
      window.clearTimeout(pending);
      pending = window.setTimeout(() => { last = Date.now(); fnRef.current(); }, wait);
    });
    return () => { unsub(); window.clearTimeout(pending); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscribe, prefixes.join("|"), throttleMs]);
}
