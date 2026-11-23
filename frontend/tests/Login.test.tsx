import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Login } from "../src/components/Login";

function mockFetch(status: number) {
  const fn = vi.fn(async () => new Response(null, { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

function submit(token: string) {
  fireEvent.change(screen.getByLabelText("アクセストークン"), { target: { value: token } });
  fireEvent.click(screen.getByRole("button", { name: /ログイン/ }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Login", () => {
  it("正しいトークンなら onSuccess を呼び、トークンは POST 本文でのみ送る", async () => {
    const fetchFn = mockFetch(204);
    const onSuccess = vi.fn();
    render(<Login onSuccess={onSuccess} />);
    submit("secret-token");
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/login");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(JSON.parse(String(init.body))).toEqual({ token: "secret-token" });
  });

  it("401 ならエラーを表示する", async () => {
    mockFetch(401);
    render(<Login onSuccess={vi.fn()} />);
    submit("wrong");
    expect(await screen.findByRole("alert")).toHaveTextContent("トークンが違います");
  });

  it("429 なら待つよう表示する", async () => {
    mockFetch(429);
    render(<Login onSuccess={vi.fn()} />);
    submit("x");
    expect(await screen.findByRole("alert")).toHaveTextContent("試行回数");
  });

  it("空のまま送信できない", () => {
    const fetchFn = mockFetch(204);
    render(<Login onSuccess={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /ログイン/ }));
    expect(fetchFn).not.toHaveBeenCalled();
  });
});
