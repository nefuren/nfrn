import { useEffect, useRef, useState } from "react";
import { checkSession as defaultCheckSession } from "../lib/api";
import type { ConnectionStatus, SlowMessage, TickMessage } from "../lib/types";

interface Options {
  onUnauthorized: () => void;
  checkSession?: () => Promise<boolean>;
  WebSocketImpl?: typeof WebSocket;
}

export interface DeskState {
  status: ConnectionStatus;
  tick: TickMessage | null;
  slow: SlowMessage | null;
}

const MAX_BACKOFF_MS = 15_000;

function parse(data: unknown): TickMessage | SlowMessage | null {
  if (typeof data !== "string") return null;
  let msg: unknown;
  try {
    msg = JSON.parse(data);
  } catch {
    return null;
  }
  if (typeof msg !== "object" || msg === null) return null;
  const type = (msg as { type?: unknown }).type;
  if (type === "tick" || type === "slow") return msg as TickMessage | SlowMessage;
  return null;
}

/** 同一オリジンの /ws に接続し、切れたらセッションを確認して再接続する。 */
export function useDeskSocket({ onUnauthorized, checkSession, WebSocketImpl }: Options): DeskState {
  const [state, setState] = useState<DeskState>({ status: "connecting", tick: null, slow: null });
  const onUnauthorizedRef = useRef(onUnauthorized);
  const checkRef = useRef(checkSession ?? defaultCheckSession);
  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
    checkRef.current = checkSession ?? defaultCheckSession;
  });

  useEffect(() => {
    const WS = WebSocketImpl ?? WebSocket;
    let ws: WebSocket | null = null;
    let disposed = false;
    let backoff = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      ws = new WS(`${scheme}://${location.host}/ws`);
      ws.onopen = () => {
        backoff = 1000;
        setState((s) => ({ ...s, status: "live" }));
      };
      ws.onmessage = (e: MessageEvent) => {
        const msg = parse(e.data);
        if (!msg) return;
        setState((s) => (msg.type === "tick" ? { ...s, tick: msg } : { ...s, slow: msg }));
      };
      ws.onclose = async () => {
        if (disposed) return;
        setState((s) => ({ ...s, status: "reconnecting" }));
        if (!(await checkRef.current())) {
          if (!disposed) onUnauthorizedRef.current();
          return;
        }
        if (disposed) return;
        timer = setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [WebSocketImpl]);

  return state;
}
