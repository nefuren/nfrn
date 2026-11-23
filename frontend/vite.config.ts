import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const BACKEND = "127.0.0.1:8787";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // 開発時は API と WebSocket をバックエンドへ中継する（Origin は 5173 のまま届く）
    proxy: {
      "/api": { target: `http://${BACKEND}` },
      "/ws": { target: `ws://${BACKEND}`, ws: true },
    },
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
  build: {
    outDir: "dist",
    sourcemap: false,
    // CSP (script-src 'self') に合わせ、インライン script を出さない
    assetsInlineLimit: 0,
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
  },
});
