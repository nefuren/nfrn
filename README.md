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

コマンドはすべて **PowerShell**（Windows ターミナル）で実行します。管理者権限が必要なのは「2. ログイン履歴を読むための権限」だけで、ダッシュボード自体は普段のアカウントで動かします。

### 0. 前提ソフト（入っていなければ）

| ソフト | 確認コマンド | インストール例 |
|---|---|---|
| Git | `git --version` | `winget install -e --id Git.Git` |
| Python 3.11 以上 | `python --version` | `winget install -e --id Python.Python.3.13` |
| Node.js 22 以上 | `node --version` | `winget install -e --id OpenJS.NodeJS.LTS` |

インストールしたら **PowerShell を開き直して**ください（PATH の変更は新しいウィンドウから有効になります）。python.org のインストーラーを使う場合は、最初の画面で **「Add python.exe to PATH」にチェック**を入れてください。

> `py` コマンド（Python ランチャー）は環境によって入っていないため、この手順では `python` を使います。

### 1. 取得と準備

```powershell
git clone https://github.com/nefuren/nfrn
cd nfrn
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -e backend
Copy-Item .env.example .env
backend\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
notepad .env
```

最後のコマンドでメモ帳が開いたら、`DESK_TOKEN=` の**すぐ右（同じ行・空白なし）**に、表示されたトークンを貼り付けて保存します（Ctrl + S）。

- メモ帳で新しいタブに貼ってしまうと、そのタブ名がトークンになって画面に表示されます。必ず `.env` のタブに貼ってください。
- トークンが写った画面を誰かに見せてしまったら、作り直して `.env` を書き換えてください。

### 2. ログイン履歴を読むための権限（初回のみ・管理者）

Windows のセキュリティログ（4625 ログオン失敗など）を読むために、自分のアカウントを「Event Log Readers」グループに入れます。増える権限は**イベントログの読み取りだけ**です（設定の変更やログの削除はできません）。

1. **Windows キー + X** を押し、「**ターミナル（管理者）**」を選んで「はい」を押します
2. 開いたウィンドウのタイトルに「管理者」と出ていることを確認し、次を実行します（`$env:USERNAME` は**書き換えずにそのまま**入力します。今のユーザー名に自動で置き換わります）

```powershell
Add-LocalGroupMember -SID S-1-5-32-573 -Member $env:USERNAME
Get-LocalGroupMember -SID S-1-5-32-573
```

3. 一覧に自分のアカウントが出れば成功です。管理者ウィンドウを閉じ、**サインアウトしてサインインし直して**ください
4. 元に戻すときは、管理者ウィンドウで `Remove-LocalGroupMember -SID S-1-5-32-573 -Member $env:USERNAME`

- グループ名ではなく SID（`S-1-5-32-573`）で指定しているので、日本語版 Windows でもそのまま通ります。
- 普段のアカウントが標準ユーザーで、管理者ウィンドウが別の管理者アカウントで開く場合は、普段の PowerShell で `whoami` を実行し、表示された `PC名\ユーザー名` を `-Member "PC名\ユーザー名"` のように指定してください。
- この手順を飛ばしても起動はできます（ログイン失敗のパネルに「権限がありません」と出て、ログイン履歴だけが表示されません）。
- ログオン失敗が記録されていない場合は、監査ポリシーを確認してください（管理者）: `auditpol /get /subcategory:"{0CCE9215-69AE-11D9-BED3-505054503030}"`

### 3. 国判定の DB（任意）

まず自動取得を試します。

```powershell
backend\.venv\Scripts\python scripts\fetch_geoip.py
```

`HTTP Error 403: Forbidden` で失敗する場合は、配布元が自動ダウンロードを拒否しています。ブラウザで手動ダウンロードしてください。

1. https://db-ip.com/db/download/ip-to-country-lite を開き、**MMDB** 形式（`dbip-country-lite-YYYY-MM.mmdb.gz`）をダウンロードします
2. ダウンロードフォルダに保存されたら、`nfrn` フォルダで次を実行します（展開して `backend\data\dbip-country-lite.mmdb` に配置します）

```powershell
backend\.venv\Scripts\python -c "import gzip,shutil,glob,os; src=sorted(glob.glob(os.path.expanduser('~/Downloads/dbip-country-lite-*.mmdb.gz')))[-1]; os.makedirs('backend/data',exist_ok=True); shutil.copyfileobj(gzip.open(src),open('backend/data/dbip-country-lite.mmdb','wb')); print('OK', src)"
```

DB が無くても動作し、国は `??` と表示されます（IP Geolocation by [DB-IP](https://db-ip.com)、CC BY 4.0）。

### 4. 画面のビルド（初回と、画面を更新したときだけ）

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
```

`npm` ではなく **`npm.cmd`** を使います。PowerShell の既定の実行ポリシーでは `npm`（実体は `npm.ps1`）が「スクリプトの実行が無効」で止められるためです。実行ポリシー自体は変更しないでください。

### 5. 起動・停止・更新

```powershell
cd backend
.\.venv\Scripts\python -m app
```

`Uvicorn running on http://127.0.0.1:8787` と出たら、ブラウザで `http://127.0.0.1:8787/` を開き、`.env` のトークンでログインします。

- このウィンドウは開いたままにします。**止めるときは Ctrl + C** です。
- 次回からは `cd $HOME\nfrn\backend` → `.\.venv\Scripts\python -m app` だけで起動できます。
- 新しい版にするときは、`nfrn` フォルダで `git pull` → `backend\.venv\Scripts\python -m pip install -e backend` → 4. のビルドをやり直します。

### つまずいたとき

| 表示されたエラー | 原因と対処 |
|---|---|
| 用語 'py' は…認識されません | Python ランチャーが無い。`python` を使う（0. を参照） |
| 用語 'python' は…認識されません／Microsoft Store が開く | Python が入っていないか PATH が通っていない。0. の手順でインストールし、PowerShell を開き直す |
| モジュール 'backend' を読み込むことができません | 仮想環境（`backend\.venv`）がまだ無い。1. の `python -m venv backend\.venv` から実行する |
| このシステムではスクリプトの実行が無効になっているため… | `npm` ではなく `npm.cmd` を使う |
| Add-LocalGroupMember : アクセスは拒否されました | 管理者ではないウィンドウで実行している。Windows キー + X →「ターミナル（管理者）」で実行する |
| 引数が null または空です（`-Member $env:...`） | `$env:USERNAME` を自分の名前に書き換えている。そのまま入力する |
| HTTP Error 403: Forbidden（fetch_geoip.py） | 3. の手動ダウンロードを使う |
| 設定エラーのため起動しません | 表示された内容に従って `.env` を直す（`DESK_TOKEN` が空・短い、など） |

助けを求めるためにエラー画面のスクリーンショットを共有するときは、**トークン（`.env` の中身）を絶対に写さない**でください。PC 名・ユーザー名・IP アドレスも隠しておくと安心です。

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

## ライセンス

このリポジトリのコードは [MIT License](LICENSE) で公開しています。

- 国判定に使う GeoIP データ（DB-IP Lite）はこのリポジトリに含まれておらず、別のライセンス（[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)、IP Geolocation by [DB-IP](https://db-ip.com)）に従います。
- 依存ライブラリはそれぞれのライセンスに従います。
