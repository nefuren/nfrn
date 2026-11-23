// REST API。Cookie（HttpOnly）は同一オリジンでのみ送る。

export type LoginResult = "ok" | "invalid" | "rate_limited" | "error";

export async function login(token: string): Promise<LoginResult> {
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (res.status === 204) return "ok";
    if (res.status === 401 || res.status === 422) return "invalid";
    if (res.status === 429) return "rate_limited";
    return "error";
  } catch {
    return "error";
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
  } catch {
    /* 失敗しても画面はログインに戻す */
  }
}

export async function checkSession(): Promise<boolean> {
  try {
    const res = await fetch("/api/session", { credentials: "same-origin" });
    if (!res.ok) return false;
    const body: unknown = await res.json();
    return typeof body === "object" && body !== null && (body as { authenticated?: unknown }).authenticated === true;
  } catch {
    return false;
  }
}
