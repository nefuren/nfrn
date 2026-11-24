# IP TEST DESK

自分の PC（Windows 11 / Linux）のセキュリティ状態をリアルタイムで監視する、ローカル専用の Web ダッシュボードです。

- 既定で `127.0.0.1` だけで待ち受け、外部には公開しません（公開するには明示的な設定が必要。下の「外部に公開する場合」を参照）
- トークン認証（HttpOnly Cookie）＋ WebSocket の Origin 確認 ＋ Host ヘッダ確認
- 通信先 IP は外部サービスへ送りません（国判定はローカルの GeoIP DB）
- 管理者権限なしで動きます

脆弱性の報告方法は [SECURITY.md](SECURITY.md) を見てください。

## 進捗

| 段階 | 状態 |
|---|---|
| 0. リポジトリ土台・セキュリティ設定 | ✅ |
| 1. バックエンド（収集・認証・WebSocket） | ✅ |
| 2. 画面の骨組み（ログイン・ヘッダー・3カラム・ネオンテーマ） | ✅ |
| 3. 各パネル（スコア・ログイン失敗・CPU/メモリ・通信量・通信先・ポート・アラート・脆弱性） | ✅ |
| 4. ネットワーク図アニメーション（D3: 自分 → 国 → IP、光る線と流れる粒、レーダー） | ✅ |

## セットアップ（Windows 11）

PowerShell で、リポジトリ直下から実行します。Python 3.11 以上が必要です。

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python -m pip install -e .
cd ..
Copy-Item .env.example .env
# トークンを作って .env の DESK_TOKEN= に貼り付ける
backend\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
notepad .env
```

### ログイン履歴を読むための権限（初回のみ）

セキュリティイベントログ（4625 ログオン失敗など）を読むには、**管理者の PowerShell** で一度だけ次を実行し、サインアウト→サインインし直してください。ダッシュボード自体は管理者で動かす必要はありません。

```powershell
Add-LocalGroupMember -Group "Event Log Readers" -Member $env:USERNAME
```

> 日本語版 Windows でもグループ名は「Event Log Readers」で通ります。通らない場合は SID 指定: `Add-LocalGroupMember -SID S-1-5-32-573 -Member $env:USERNAME`

ログオン失敗が記録されていない場合は、監査ポリシーを確認してください（管理者）:
`auditpol /get /subcategory:"{0CCE9215-69AE-11D9-BED3-505054503030}"`（ログオン）。

### 国判定の DB（任意）

```powershell
backend\.venv\Scripts\python scripts\fetch_geoip.py
```

`backend/data/dbip-country-lite.mmdb` が作られます（IP Geolocation by [DB-IP](https://db-ip.com)、CC BY 4.0）。無くても動作し、国は `??` と表示されます。

### 起動

```powershell
cd backend
.\.venv\Scripts\python -m app
```

先に画面をビルドしておきます（Node.js 22 以上が必要。初回とフロントエンド更新時のみ）:

```powershell
cd frontend
npm ci
npm run build
```

そのあとバックエンドを起動し、`http://127.0.0.1:8787/` を開いて `.env` のトークンでログインします。

## セットアップ（Linux）

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e . && cd ..
cp .env.example .env   # DESK_TOKEN を設定
sudo usermod -aG adm "$USER"   # auth.log / journal を読むため（再ログインが必要）
cd backend && .venv/bin/python -m app
```

## 外部に公開する場合（非推奨）

このダッシュボードは自分の PC から見ることを前提にしています。`DESK_HOST` をループバック（`127.0.0.0/8`・`::1`・`localhost`）以外にすると、**次の両方を設定しない限り起動しません**。

| 設定 | 理由 |
|---|---|
| `DESK_ALLOW_REMOTE=true` | ネットワークに公開することを明示的に選ぶため。書き間違いで公開してしまう事故を防ぐ |
| `DESK_COOKIE_SECURE=true` | セッション Cookie を HTTPS でしか送らせないため。平文の HTTP で盗聴されるのを防ぐ |

`DESK_COOKIE_SECURE=true` の Cookie は HTTP では送られないので、外部公開するときは必ず HTTPS のリバースプロキシ（Caddy、nginx など）を前に置いてください。あわせて `DESK_ALLOWED_HOSTS` と `DESK_ALLOWED_ORIGINS` に、公開するホスト名と `https://` の Origin を追加し、ファイアウォールで接続元を絞ってください。

## ネットワーク図の見方

- 中心が自分の PC、まわりの円が国（`LAN` はローカルネットワーク、`??` は国不明）、小さな点が通信先 IP です。
- 色: シアン=公開 IP、ライム=LAN、オレンジ=国不明、マゼンタ=アラートに出た IP（点滅）。
- 線の上を流れる粒は接続の多さに応じて速くなります。ノードにマウスを乗せるとプロセス名とポートを表示します。
- OS の「視差効果を減らす（アニメーションを減らす）」設定がオンなら、粒とレーダーは止まります。

## 開発

```bash
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m bandit -q -c pyproject.toml -r app
.venv/bin/python -m pip_audit --skip-editable
```

フロントエンドを開発モードで動かす場合（バックエンドを起動したまま別ターミナルで）:

```bash
cd frontend
npm run dev      # http://127.0.0.1:5173/ （/api と /ws は 8787 へ中継）
npm test         # vitest（XSS 対策の lint ルールのテストを含む）
npm run lint
```

コミット前に gitleaks を走らせるには `pre-commit install` を実行してください。

## 仕組み

```
backend/app/
  config.py            設定（.env / DESK_*）
  auth.py              トークン照合・セッション・試行回数制限
  security_headers.py  CSP などのヘッダ
  main.py              API と WebSocket（/api/login, /api/logout, /api/session, /api/snapshot, /ws）
  monitor.py           収集ループ（tick: 1秒 / slow: 10秒 / audit: 6時間）
  runner.py            OS コマンド実行の唯一の入口（固定引数・shell=False）
  collectors/          system, network, geoip, logins_windows, logins_linux, firewall, audit
  analysis/            score（減点方式）, alerts（検知ルール）
```

| データ | Windows 11 | Linux |
|---|---|---|
| CPU・メモリ・通信量・通信先・待ち受けポート | psutil | psutil |
| ログイン失敗/成功/ロック | `wevtutil`（4625/4624/4740） | auth.log / journalctl |
| ファイアウォール | レジストリ（GPO 優先） | 未対応 |
| 依存ライブラリの脆弱性 | pip-audit / npm audit | 同左 |

### API を直接呼ぶ場合

`/api/login` と `/api/logout` は、`Origin` ヘッダーが `DESK_ALLOWED_ORIGINS` に含まれていないと `403` を返します（`Origin` が無い場合も拒否）。
ブラウザは自動で付けますが、curl などで呼ぶときは `-H "Origin: http://127.0.0.1:8787"` のように明示してください。WebSocket（`/ws`）も同じルールです。

### WebSocket メッセージ

- `{"type":"tick", system, net, remotes, connections_total, score}` … 1秒ごと
- `{"type":"slow", host, ports, firewall, logins, alerts, audit, score}` … 10秒ごと

## GitHub での設定

- **Settings → Code security** で Dependabot alerts / security updates、Private vulnerability reporting を有効化
- CodeQL・gitleaks・CI は `.github/workflows/` に定義済み（gitleaks-action は Organization リポジトリでは `GITLEAKS_LICENSE` が必要）
