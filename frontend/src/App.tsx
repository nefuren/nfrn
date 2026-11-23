import { useCallback, useEffect, useState } from "react";
import { Desk } from "./components/Desk";
import { Login } from "./components/Login";
import { checkSession, logout } from "./lib/api";

type Auth = "checking" | "anon" | "authed";

export function App() {
  const [auth, setAuth] = useState<Auth>("checking");

  useEffect(() => {
    checkSession().then((ok) => setAuth(ok ? "authed" : "anon"));
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    setAuth("anon");
  }, []);
  const handleUnauthorized = useCallback(() => setAuth("anon"), []);

  if (auth === "checking") return <div className="boot">BOOTING…</div>;
  if (auth === "anon") return <Login onSuccess={() => setAuth("authed")} />;
  return <Desk onUnauthorized={handleUnauthorized} onLogout={handleLogout} />;
}
