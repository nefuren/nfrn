# IP TEST DESK

自分の PC（Windows 11 / Linux）のセキュリティ状態をリアルタイムで監視する、ローカル専用の Web ダッシュボードです。

- 既定で `127.0.0.1` だけで待ち受け、外部には公開しません
- トークン認証（HttpOnly Cookie）＋ WebSocket の Origin 確認 ＋ Host ヘッダ確認
- 通信先 IP は外部サービスへ送りません（国判定はローカルの GeoIP DB）
- 管理者権限なしで動きます

脆弱性の報告方法は [SECURITY.md](SECURITY.md) を見てください。

## 進捗

| 段階 | 状態 |
|---|---|
| 0. リポジトリ土台・セキュリティ設定 | ✅ |
| 1. バックエンド（収集・認証・WebSocket） | ✅ |
| 2. 画面の骨組み | ⏳ |
| 3. 各パネル | ⏳ |
| 4. ネットワーク図アニメーション | ⏳ |

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

`http://127.0.0.1:8787/` を開き、`.env` のトークンでログインします。（画面は段階2以降で追加されます。今は API のみ。）

## セットアップ（Linux）

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e . && cd ..
cp .env.example .env   # DESK_TOKEN を設定
sudo usermod -aG adm "$USER"   # auth.log / journal を読むため（再ログインが必要）
cd backend && .venv/bin/python -m app
```

## 開発

```bash
cd backend
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m bandit -q -c pyproject.toml -r app
.venv/bin/python -m pip_audit --skip-editable
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

### WebSocket メッセージ

- `{"type":"tick", system, net, remotes, connections_total, score}` … 1秒ごと
- `{"type":"slow", host, ports, firewall, logins, alerts, audit, score}` … 10秒ごと

## GitHub での設定

- **Settings → Code security** で Dependabot alerts / security updates、Private vulnerability reporting を有効化
- CodeQL・gitleaks・CI は `.github/workflows/` に定義済み（gitleaks-action は Organization リポジトリでは `GITLEAKS_LICENSE` が必要）
