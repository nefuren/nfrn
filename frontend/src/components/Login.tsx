import { useState, type FormEvent } from "react";
import { login } from "../lib/api";

const MESSAGES = {
  invalid: "トークンが違います",
  rate_limited: "試行回数が多すぎます。1分ほど待ってから再試行してください",
  error: "サーバーに接続できません",
} as const;

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token.trim() || busy) return;
    setBusy(true);
    setError(null);
    const result = await login(token.trim());
    setBusy(false);
    if (result === "ok") {
      setToken("");
      onSuccess();
    } else {
      setError(MESSAGES[result]);
    }
  }

  return (
    <main className="login">
      <form className="login-card panel panel--cyan" onSubmit={submit}>
        <h1 className="logo logo--big">
          IP TEST <span className="logo__accent">DESK</span>
        </h1>
        <p className="login-sub">SECURITY MONITOR // LOCAL ACCESS ONLY</p>
        <label className="field">
          <span className="field__label">アクセストークン</span>
          <input
            className="field__input"
            type="password"
            autoComplete="current-password"
            spellCheck={false}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoFocus
          />
        </label>
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? "確認中…" : "ログイン"}
        </button>
        <p className="login-hint">トークンは .env の DESK_TOKEN です</p>
      </form>
    </main>
  );
}
