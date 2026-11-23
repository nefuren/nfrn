import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDeskSocket } from "../src/hooks/useDeskSocket";

class FakeWS {
  static last: FakeWS | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeWS.last = this;
  }
  close() {
    this.closed = true;
  }
}

function Probe(props: { onUnauthorized: () => void; checkSession: () => Promise<boolean> }) {
  const s = useDeskSocket({
    onUnauthorized: props.onUnauthorized,
    checkSession: props.checkSession,
    WebSocketImpl: FakeWS as unknown as typeof WebSocket,
  });
  return (
    <div>
      <span data-testid="status">{s.status}</span>
      <span data-testid="cpu">{s.tick?.system.cpu ?? "-"}</span>
      <span data-testid="host">{s.slow?.host.hostname ?? "-"}</span>
    </div>
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWS.last = null;
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const tick = { type: "tick", ts: "t", system: { cpu: 42 }, net: {}, remotes: [], connections_total: 0, score: {} };
const slow = { type: "slow", ts: "t", host: { hostname: "pc" } };

describe("useDeskSocket", () => {
  it("同じホストの /ws に接続し、tick / slow を反映する", () => {
    render(<Probe onUnauthorized={vi.fn()} checkSession={async () => true} />);
    const ws = FakeWS.last!;
    expect(ws.url).toBe(`ws://${location.host}/ws`);
    act(() => ws.onopen?.());
    expect(screen.getByTestId("status")).toHaveTextContent("live");
    act(() => ws.onmessage?.({ data: JSON.stringify(tick) }));
    act(() => ws.onmessage?.({ data: JSON.stringify(slow) }));
    expect(screen.getByTestId("cpu")).toHaveTextContent("42");
    expect(screen.getByTestId("host")).toHaveTextContent("pc");
  });

  it("壊れた JSON や未知の type は無視する", () => {
    render(<Probe onUnauthorized={vi.fn()} checkSession={async () => true} />);
    const ws = FakeWS.last!;
    act(() => ws.onopen?.());
    act(() => ws.onmessage?.({ data: "{not json" }));
    act(() => ws.onmessage?.({ data: JSON.stringify({ type: "evil", system: { cpu: 99 } }) }));
    act(() => ws.onmessage?.({ data: 12345 }));
    expect(screen.getByTestId("cpu")).toHaveTextContent("-");
  });

  it("切断後セッションが無効なら onUnauthorized", async () => {
    const onUnauthorized = vi.fn();
    render(<Probe onUnauthorized={onUnauthorized} checkSession={async () => false} />);
    await act(async () => FakeWS.last!.onclose?.({ code: 1006 }));
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("切断後セッションが有効なら再接続する", async () => {
    render(<Probe onUnauthorized={vi.fn()} checkSession={async () => true} />);
    const first = FakeWS.last!;
    await act(async () => first.onclose?.({ code: 1006 }));
    expect(screen.getByTestId("status")).toHaveTextContent("reconnecting");
    await act(async () => vi.advanceTimersByTime(1500));
    expect(FakeWS.last).not.toBe(first);
  });
});
