# IP TEST DESK — 設計書

## 目的
自分の Windows 11 PC（将来は Linux VPS も）のセキュリティ状態を、ローカルのWebダッシュボードでリアルタイムに監視する。
監視ツール自体が攻撃面にならないことを最優先とする。

## ゴール / 非ゴール / アンチゴール
- ゴール: 実データ（CPU・メモリ・通信量・通信先・待ち受けポート・ログイン失敗・依存脆弱性）を1秒周期で表示。サイバーパンク調の3カラムUIと中央のネットワーク図。
- 非ゴール: 複数台の集中監視、外部公開、自動遮断（ファイアウォール操作など書き込み系の操作）。
- アンチゴール: ダッシュボードが外部から見える／トークンなしで読める／ログ由来の文字列でXSSが起きる／任意コマンドが実行できる／IPを外部APIへ送信する。

## 構成
- backend: Python 3.11+ / FastAPI / uvicorn / psutil / pydantic-settings / defusedxml / maxminddb
- frontend: React + Vite + TypeScript / ECharts / D3（ネットワーク図）
- 本番: `vite build` の成果物を FastAPI が同一オリジンで配信。開発: Vite dev server → backend へプロキシ。

## アプローチ（検討した案）
- 図: D3(SVG, 採用) / Three.js。D3 はラベルを textContent で安全に描け、常時描画の負荷が低い。Three.js は見栄えは良いがテキスト描画と負荷が重い。
- グラフ: ECharts(採用) / Lightweight Charts。ゲージ・棒・線を1ライブラリでまかなえるため ECharts。
- 認証の受け渡し: HttpOnly Cookie(採用) / URLクエリ / WS subprotocol。URLはログに残る。Cookie + Origin検証で CSWSH を防ぐ。
- Windowsログ: wevtutil + defusedxml(採用) / pywin32。ネイティブ依存なし、サンプルXMLで Linux 上でもテスト可能。

## セキュリティ設計
- 既定 bind `127.0.0.1:8787`。非ループバック指定時は起動時に警告。
- `DESK_TOKEN`（.env、32文字以上必須）。`POST /api/login` で `hmac.compare_digest` 比較 → ランダムなセッションIDを HttpOnly・SameSite=Strict Cookie で発行（メモリ保持・有効期限付き）。ログインはIP単位でレート制限。
- WebSocket: Origin が `DESK_ALLOWED_ORIGINS` に含まれ、かつ有効なセッションCookieがある場合のみ accept。
- レスポンスヘッダ: CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY`。
- 表示: 外部データは React テキストノード / SVG textContent のみ。ESLint で innerHTML 系・dangerouslySetInnerHTML を禁止。
- コマンド: `runner.py` に許可コマンドの固定引数リストを定義し、名前で呼ぶだけ。`shell=False`・タイムアウト・出力サイズ上限。bandit で `shell=True` を検出。
- GeoIP はローカル mmdb（DB-IP Lite country）。ファイルが無ければ国は「?」。
- 秘密は `.env`（gitignore）、`.env.example` のみコミット。gitleaks（pre-commit + CI）、pip-audit、npm audit、Dependabot、CodeQL、bandit、ruff、pytest、vitest。

## データ収集（OS別プラグイン）
| 項目 | Windows 11 | Linux |
|---|---|---|
| CPU/メモリ/通信量/通信先 | psutil | psutil |
| 待ち受けポート | psutil（+ `netstat -ano`） | psutil（+ `ss -Htunlp`） |
| ログイン失敗 | `wevtutil` Security 4625/4624/4740 | auth.log / journalctl |
| FW 状態 | `netsh advfirewall show allprofiles state` | （ufw は任意） |
| 依存脆弱性 | pip-audit / npm audit（6時間毎、キャッシュ） | 同左 |

権限: Windows は「Event Log Readers」グループ、Linux は adm グループ。管理者/root で実行しない。

## 分析
- スコア: 100点減点方式。内訳（FW無効、0.0.0.0 待ち受けの危険ポート、直近1時間のログイン失敗、脆弱性件数×重大度）を返す。
- アラート: 同一IPから5分で5回以上の失敗、新規待ち受けポート出現、管理者アカウントへの失敗、危険ポートへの外向き通信。

## WebSocket メッセージ
`{"type":"tick", ...}` 1秒毎（cpu, mem, net, connections, score）、`{"type":"slow", ...}` 10秒毎（ports, logins, alerts, audit）。

## 段階
0. リポジトリ土台とセキュリティ設定 1. バックエンド 2. 画面骨組み 3. 各パネル 4. ネットワーク図アニメーション

## 残りは実装者判断
パネルの細かいレイアウト、色の配分、閾値の細かな値。
