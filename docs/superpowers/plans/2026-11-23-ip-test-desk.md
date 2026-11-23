# IP TEST DESK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ローカル専用・トークン認証付きのセキュリティ監視ダッシュボード（Windows 11 主対象、Linux 併用）。

**Architecture:** FastAPI バックエンドが OS 別コレクタでデータを集め、Monitor が 1 秒 / 10 秒周期でスナップショットを作り WebSocket で配信。React + Vite フロントが ECharts と D3 で描画。本番は FastAPI が dist を同一オリジンで配信。

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, psutil, pydantic-settings, defusedxml, maxminddb, pytest / React 18, Vite, TypeScript, ECharts, D3, vitest

**Spec:** `docs/superpowers/specs/2026-11-23-ip-test-desk-design.md`

## Global Constraints
- 既定 bind `127.0.0.1:8787`。`DESK_TOKEN` は 32 文字以上、無ければ起動しない。
- `subprocess` は `app/runner.py` だけが使う。`shell=False`、引数は `COMMANDS` の固定タプルのみ、可変なのは `cwd` だけ。
- 外部データを HTML として挿入しない（innerHTML / dangerouslySetInnerHTML 禁止）。
- IP を外部サービスへ送らない（GeoIP はローカル mmdb）。
- 管理者 / root 権限を前提にしない。
- `.env` はコミットしない。

## Review Focus
1. Windows 日本語ロケール: イベントログ・コマンド出力に日本語（ユーザー名など）が含まれても文字化けで落ちない → runner の decode テスト。
2. ログが読めない（権限なし・ファイル無し）: 例外で配信が止まらず、パネルに「権限なし」と出る → logins コレクタの status テスト。
3. Host ヘッダ偽装（DNS rebinding）: 127.0.0.1/localhost 以外の Host を拒否 → test_host_header_rejected。
4. 悪意ある文字列（`<script>` を含むユーザー名）: そのままの文字列として JSON に載る（加工・解釈しない）→ parser テスト。
5. pip-audit / npm が未インストール: 監査パネルが「未実行（ツールなし）」になり他は動く → audit テスト。

---

## Stage 0: リポジトリ土台とセキュリティ設定

### Task 0.1: リポジトリ衛生と CI
**Files:** Create `.gitignore`, `.env.example`, `.gitleaks.toml`, `.pre-commit-config.yaml`, `.github/dependabot.yml`, `.github/workflows/ci.yml`, `.github/workflows/codeql.yml`, `.github/workflows/gitleaks.yml`, `SECURITY.md`, `README.md`
- [ ] `.gitignore` に `.env`, `*.mmdb`, `node_modules/`, `dist/`, `.venv/`, `__pycache__/`
- [ ] ci.yml: backend job（ubuntu-latest と windows-latest の matrix: ruff, bandit -r app, pytest, pip-audit）、frontend job（`hashFiles('frontend/package-lock.json')` がある時のみ: npm ci, lint, test, build, `npm audit --audit-level=high`）
- [ ] codeql.yml（python, javascript-typescript）、gitleaks.yml、dependabot（pip: /backend, npm: /frontend, github-actions: /、weekly）
- [ ] SECURITY.md: 報告窓口（GitHub Private vulnerability reporting）、対応目標（受領 3 日・評価 7 日・Critical 修正 14 日）、対象範囲
- [ ] Commit `chore: repository security baseline`

## Stage 1: バックエンド

### Task 1.1: 設定と runner
**Files:** `backend/pyproject.toml`, `backend/app/config.py`, `backend/app/runner.py`, tests `test_config.py`, `test_runner.py`
**Produces:** `Settings`（env_prefix `DESK_`: token: SecretStr, host, port, allowed_origins: list[str], allowed_hosts: list[str], session_ttl_seconds=43200, cookie_secure=False, geoip_db: Path|None, auth_log=/var/log/auth.log, audit_paths: list[Path], audit_interval_seconds=21600）; `runner.run(name: str, cwd: Path|None=None, timeout: float=30) -> CommandResult(returncode:int, stdout:str, stderr:str)`; `CommandUnavailable`, `UnknownCommand`
- [ ] テスト: 短いトークンで ValidationError / カンマ区切りリストを解析 / 未知コマンド名で UnknownCommand / `subprocess.run` が `shell=False` とタプル由来の list で呼ばれる / 出力が UTF-8 でなくても decode が例外を出さない
- [ ] 実装（`COMMANDS: dict[str, tuple[str, ...]]`、先頭 `"{python}"` は `sys.executable`、`shutil.which` で絶対パス解決、出力 5MB 上限）→ pass → commit

### Task 1.2: 認証・セキュリティヘッダ・アプリ本体
**Files:** `app/auth.py`, `app/security_headers.py`, `app/main.py`, `app/__main__.py`, tests `test_auth.py`, `test_headers.py`, `test_ws.py`
**Produces:** `create_app(settings: Settings, monitor: MonitorProtocol | None = None) -> FastAPI`; `SessionStore.create() -> str`, `.valid(sid) -> bool`, `.revoke(sid)`; `RateLimiter.allow(key) -> bool`（1 分 5 回）; Cookie 名 `desk_session`
- [ ] テスト: 正トークンで 204 + HttpOnly/SameSite=Strict Cookie / 誤りで 401 / 6 回目で 429 / 未認証 `/api/snapshot` 401 / 全応答に CSP・nosniff・no-referrer・X-Frame-Options / 不正 Host で 400 / WS: Cookie なし拒否・Origin 不一致拒否・両方 OK で `tick` 受信 / `/docs` が 404
- [ ] 実装 → pass → commit

### Task 1.3: コレクタ
**Files:** `app/collectors/{system,network,ports,geoip,logins_windows,logins_linux,firewall,audit}.py`, `app/collectors/history.py`, tests 各 `test_*.py` + `tests/fixtures/`
**Produces:** `SystemCollector.sample() -> dict`; `NetRate.sample() -> dict(rx_bps, tx_bps, rx_total, tx_total)`; `collect_connections(geo) -> list[dict]`（remote 単位集約）; `collect_listening() -> list[dict](proto,address,port,pid,process,exposed)`; `GeoIP.lookup(ip) -> str`（"LAN"/"LOCAL"/"??"/ISO）; `parse_windows_events(xml:str) -> list[LoginEvent]`; `parse_auth_log(text:str, year:int) -> list[LoginEvent]`; `LoginHistory.add(events) -> list[LoginEvent]`（新規のみ返す）, `.failures_per_minute(now, minutes=60) -> list[int]`; `firewall_state() -> dict(profiles: dict[str,bool|None])`; `parse_pip_audit(json) / parse_npm_audit(json) -> list[Finding]`; `LoginEvent(ts, kind: "failure"|"success"|"lockout", user, source_ip, detail)`
- [ ] テスト: 4625/4624/4740 XML fixture（`<script>` を含むユーザー名、日本語ユーザー名を含む）/ syslog 形式・RFC3339 形式の auth.log / 重複除去 / 分ごとの集計 / private→LAN / pip・npm JSON fixture / ツール無しで status="unavailable"
- [ ] 実装 → pass → commit

### Task 1.4: 分析と Monitor
**Files:** `app/analysis/score.py`, `app/analysis/alerts.py`, `app/monitor.py`, tests `test_score.py`, `test_alerts.py`, `test_monitor.py`
**Produces:** `compute_score(ctx: ScoreContext) -> dict(value:int, items:list[{label, points}])`; `AlertEngine.evaluate(now, new_events, listening, connections) -> list[Alert]`; `Monitor.start()/stop()/tick()/slow()/snapshot()`
- 減点: FW 無効プロファイル -25 / 危険ポート公開 -5 個（上限 -15）/ その他公開ポート -1 個（上限 -5）/ 1 時間の失敗 ≥10 で -15、≥1 で -5 / 24 時間内ロックアウト -10 / 脆弱性 critical -10・high -5・moderate -2・その他 -1（上限 -30）/ ダッシュボード自身が非ループバック -20。0〜100 に丸め。
- アラート: 同一 IP 5 分で 5 回以上失敗（crit、IP ごと 10 分クールダウン）/ administrator・admin・root への失敗（warn）/ ロックアウト（crit）/ 初回以降の新規待ち受けポート（warn）/ 外向き 23,4444,5555,6667,1337,31337（warn）
- [ ] テスト → 実装 → pass → commit、`python -m app` で実データの tick が流れることを手動確認

## Stage 2: 画面の骨組み
### Task 2.1: Vite + React + TS、ESLint（no-danger, no-restricted-properties innerHTML/outerHTML, no-restricted-syntax insertAdjacentHTML）、ログイン画面、`useDeskSocket()`（再接続付き）、ヘッダー + 3 カラム + ネオンテーマ、Vite proxy（/api, /ws → 8787）
- [ ] vitest: ログイン失敗表示、ソケットのメッセージ反映 → commit

## Stage 3: 各パネル
### Task 3.1: 左（スコアゲージ+内訳、ログイン失敗の推移、CPU/メモリ）、中央上（通信量グラフ）、右（ポート表、アラート履歴、脆弱性）。ECharts、外部文字列はテキストのみ → vitest（`<script>` 文字列がテキストとして出る）→ commit

## Stage 4: ネットワーク図
### Task 4.1: D3 force、中心ノード=自マシン、リモート IP ノード（国コード・接続数）、光る線と流れるパーティクル、新規ノードのフェードイン、ラベルは textContent → commit
