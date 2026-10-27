<!-- template-version: 3 (2026-10-27) / 正本: agent-skills の review-workflow:threat-coverage skill（template.md） -->
<!-- threat-coverage skill が docs/reference/security-threat-coverage.md に置き、版の差を同期する。ID 列は同期のキーなので消さない・変えない。リポ独自の行は ID を local. で始める。該当しない層の表は状態を「対象外」にして残す -->
# 攻撃の種類ごとの対策状況

このリポが「どの攻撃に対策しているか／どこが弱いか」の正本。分類は OWASP API Security Top 10（2023）・OWASP Top 10（2025）・OWASP Top 10 for LLM（2025）・Electron 公式セキュリティチェックリスト・SLSA に沿って網羅し、点検していない分類も「未点検」として残す。

- 根拠: <!-- 点検・監査の日付と issue -->
- 記号: ✅ 対策あり / △ 部分的 / ❌ 対策なし / ― 未点検 / 対象外
- 修正したら該当行の状態と issue を更新する。攻撃の手順はここに書かない（弱点と対策だけ）
- 公開リポに置かない（未修正の穴の一覧になる）

## API・Web バックエンド

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `api.bola` | 他社・他人のデータを ID 指定で読む（BOLA・テナント越境） | テナントのスコープが fail-closed か、Policy で所有を確かめるか | ― | | |
| `api.baas-rls` | BaaS（Supabase 等）の RLS 漏れで DB を直接読み書きされる | 公開スキーマの全テーブル・RPC・Storage で RLS が有効か、anon / authenticated に過剰な許可が無いか（vuln-scan の層5） | ― | | |
| `api.authn` | 認証の突破（総当たり・トークン窃取） | throttle、トークンのハッシュ保存・期限・失効 | ― | | |
| `api.admin-takeover` | 管理画面の乗っ取り | MFA、管理者の分離、ログインの監査 | ― | | |
| `api.bfla` | 権限の昇格（BFLA） | 役割の middleware・Policy が全ルートにあるか | ― | | |
| `api.client-analysis` | 公開アプリを解析して隠れた API を叩く（A2B攻撃） | 画面に出ない API にも認証・認可があるか、アプリに接続先の鍵を埋めないか、旧版の API を閉じたか | ― | | |
| `api.server-action` | フレームワークが自動で公開するサーバー関数の認可抜け（Next.js Server Actions 等） | 関数ごとに認証・認可・入力検証をするか、middleware だけに頼らないか、Client へ機密を渡さないか | ― | | |
| `api.bopla` | 項目の書き換え・過剰な応答（BOPLA） | mass assignment、応答の項目の絞り込み | ― | | |
| `api.resource` | 資源の食いつぶし | rate limit、ページサイズ・件数の上限 | ― | | |
| `api.business-flow` | 業務フローの悪用 | 通知・課金・外部送信の連打 | ― | | |
| `api.race-condition` | 同時実行による二重消費・二重確定 | 残高・在庫・クーポン・一度限りの操作を DB 制約・行ロック・原子的更新・冪等キーで守るか | ― | | |
| `api.m2m-spoof` | 機械どうしの API のなりすまし | 静的な共有トークンか、呼び出し元の身元と対象を結び付けるか、定数時間の比較か | ― | | |
| `api.unsafe-consumption` | Webhook の再送・連携先 API の応答の盲信 | 署名に加えて時刻とイベント ID で再送を弾くか、外部 API の応答も未信頼として検証するか | ― | | |
| `api.injection` | SQL / コマンド / テンプレートのインジェクション | raw SQL のバインド、シェルを通さない実行、エスケープしない出力 | ― | | |
| `api.deserialization` | 危険なデシリアライズ | 外部データの復元で型・クラスを相手に指定させないか | ― | | |
| `api.xss` | XSS | 生 HTML の出力、iframe の sandbox、CSP | ― | | |
| `api.ssrf` | SSRF | 利用者が決める URL を取得していないか | ― | | |
| `api.path-traversal` | パストラバーサル | ファイル名の検証、realpath で配下か確かめる | ― | | |
| `api.upload` | ファイルアップロードの悪用 | 種類・サイズ・保存先、公開範囲 | ― | | |
| `api.csrf-cors` | CSRF / CORS | CSRF トークン、CORS の origin と credentials | ― | | |
| `api.misconfig` | 設定ミス・情報露出 | デバッグ無効、セキュリティヘッダ、例外文を返さない、信頼プロキシ | ― | | |
| `api.cache-poisoning` | Web キャッシュの汚染・機密応答の共有 | 認証・テナント・入力で変わる応答が CDN やフレームワークのキャッシュで別の利用者に返らないか | ― | | |
| `api.fail-open` | 例外・障害時の素通し | 外部の認証・課金・rate limit が失敗・タイムアウトしたとき拒否に倒れるか、途中失敗で半端に確定しないか | ― | | |
| `api.session` | セッション窃取 | cookie の属性、サーバー側で失効できるか | ― | | |
| `api.secret-storage` | 秘密の保存 | 秘密の置き場、照合用の秘密を HMAC で保存、暗号化列 | ― | | |
| `api.log-leak` | ログからの漏えい | 秘密・PII をログ・通知に出さない | ― | | |
| `api.audit-log` | 監査ログの欠落 | 機微データの閲覧・管理操作・認証イベントの記録 | ― | | |
| `api.known-vulns` | 依存・ランタイムの既知の脆弱性 | vuln-scan の結果、自動更新 | ― | | |


## AI・LLM 機能

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `ai.prompt-injection` | 製品の LLM 機能へのプロンプトインジェクション | 入力・取得した文書を指示として扱わないか、LLM に渡すツールの権限、出力を実行・表示する前の検証 | ― | | |
| `ai.output-agency` | LLM 出力の未検証実行・過剰なツール権限 | 出力を SQL・シェル・HTML・外部呼び出しへ渡す前に検証するか、ツールを最小権限にし破壊的操作に人の承認を挟むか | ― | | |
| `ai.rag` | RAG の権限越境・知識ベースの汚染 | ベクトル検索でテナント・権限を絞るか、未検証の外部データを取り込まないか、取り込んだ版を戻せるか | ― | | |

## デスクトップアプリ（Electron 等）

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `desk.node-in-renderer` | Renderer から Node を直接使う | contextIsolation・nodeIntegration・sandbox | ― | | |
| `desk.navigation` | 外部ページへの遷移・新しいウィンドウ | will-navigate・setWindowOpenHandler・openExternal の URL 検証 | ― | | |
| `desk.permission` | 権限要求の悪用 | setPermissionRequestHandler | ― | | |
| `desk.xss-rce` | Renderer の XSS → 端末でのコード実行 | CSP、preload の公開範囲 | ― | | |
| `desk.ipc` | IPC の悪用 | 送信元の検証、引数の検証 | ― | | |
| `desk.file-rw` | 任意ファイルの読み書き | パスの検証 | ― | | |
| `desk.child-proc` | 子プロセスへのコマンド・環境変数の差し込み | shell を通さない、env は許可リスト | ― | | |
| `desk.stored-secret` | 保存された秘密の窃取 | OS のキーチェーン（safeStorage 等）、Renderer のストレージに写さない | ― | | |
| `desk.dev-mode` | 本番アプリを開発モード・偽の接続先で動かす | ビルド時に決まる条件（isPackaged）で分岐、接続先を固定 | ― | | |
| `desk.debug-args` | デバッグ引数で特権側を乗っ取る | Fuses（RunAsNode・NODE_OPTIONS 等も無効か）、OS の権限（TCC 等）に他プロセスが乗れないか | ― | | |
| `desk.tamper` | インストール済みアプリの改ざん | asar の完全性、インストール先の権限 | ― | | |
| `desk.remote-code` | 遠隔コードの読み込み | CDN の読み込み、SRI | ― | | |
| `desk.bundled-secret` | 配布物に同梱された秘密の抜き出し | 同梱ファイルの検証 | ― | | |
| `desk.deep-link` | deep link からの起動 | プロトコル登録と引数の検証 | ― | | |
| `desk.oauth-loopback` | OAuth の認可コードの横取り（ループバック・カスタム URI） | PKCE（S256）と state を必須にしているか | ― | | |
| `desk.script-tamper` | 配信するスクリプト・設定の改ざん | 署名・ハッシュの取得元が配信元と別経路か | ― | | |
| `desk.old-runtime` | 古いランタイムの脆弱性 | 版の追従、EOL の検知 | ― | | |

## 配布・CI（サプライチェーン）

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `ci.fake-update` | 自動更新で偽の版を配る | 全 OS のコード署名と発行者の照合、ダウングレード禁止 | ― | | |
| `ci.release-token` | リリース用トークンの悪用 | スコープ・期限・保管場所 | ― | | |
| `ci.action-tamper` | 第三者 Action の改ざん | SHA 固定、`permissions:` の最小化 | ― | | |
| `ci.workflow-injection` | 未レビュー PR の特権実行・ワークフロー注入 | pull_request_target・workflow_run で PR のコードを秘密付きで動かさないか、`${{ github.event.* }}` を run に直接展開しないか | ― | | |
| `ci.cache-poisoning` | CI のキャッシュ・成果物の汚染 | 低信頼ジョブのキャッシュ・成果物をリリース処理で検証なしに使わないか | ― | | |
| `ci.auto-merge` | 依存の自動マージの悪用 | 自動マージの対象と判定条件 | ― | | |
| `ci.malicious-dep` | 悪意ある依存の混入（乗っ取られた正規パッケージ・AI が幻覚した名前） | install スクリプトを止めるか、公開直後の版を待つか、AI が出したパッケージの実在と出所を確かめるか | ― | | |
| `ci.secret-commit` | 秘密のコミット混入 | gitleaks（vuln-scan の層4） | ― | | |

## インフラ・クラウド

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `infra.tls` | 盗聴・ダウングレード | TLS の版、HTTP→HTTPS | ― | | |
| `infra.direct-access` | 内部サービスへの直接アクセス | ingress の制限、内部経路を公開 LB で遮断 | ― | | |
| `infra.shadow-endpoints` | 検証環境・サブドメイン・旧 API の放置 | 公開中のホスト・API の棚卸し、検証環境のアクセス制限 | ― | | |
| `infra.storage-dns` | ストレージの公開・DNS の残骸からの乗っ取り | バケットの公開防止、解約済みサービスを指す CNAME が残っていないか | ― | | |
| `infra.iam` | サービスアカウント・IAM の権限の悪用 | 最小権限、条件付きロール、鍵の発行禁止 | ― | | |
| `infra.lateral` | 実行環境の侵害からの横展開 | コンテナの実行ユーザー、sandbox、テナントごとの分離 | ― | | |
| `infra.iac-secret` | IaC の state・設定に残る秘密 | state の置き場と暗号化 | ― | | |
| `infra.detection` | 侵入の検知 | 監査ログ、アラート、定期スキャン | ― | | |
| `infra.dos` | DoS・大量リクエスト | LB 前段の防御 | ― | | |
| `infra.denial-of-wallet` | 課金の食いつぶし | LLM API・クラウドの利用上限、最大インスタンス数、予算アラート | ― | | |
| `infra.backup` | バックアップの漏えい・消失 | 暗号化、削除保護、保持期間 | ― | | |

## 開発環境・人

| ID | 攻撃の種類 | 確認する観点 | 状態 | 守っている仕組み | 残っている弱点 |
|---|---|---|---|---|---|
| `dev.agent-injection` | AI エージェントへの指示注入・権限のすり抜け | 権限設定、確認なしの push・外部送信 | ― | | |
| `dev.mcp-rules` | MCP・エージェント用ルールファイルの汚染 | 外部 MCP のツール定義を版で固定・確認するか、指示ファイルの不可視文字と変更をレビューするか | ― | | |
| `dev.repo-autorun` | 開いたリポの設定による自動実行（偽の採用面接等） | 未信頼リポの IDE タスク・hook・ツール設定を自動で動かさないか | ― | | |
| `dev.dns-rebinding` | localhost の開発・MCP サーバーへの DNS リバインディング | Host・Origin の検証と認証があるか | ― | | |
| `dev.machine-secret` | 開発機の秘密の窃取 | 平文の秘密を置かない（1Password 等） | ― | | |
| `dev.phishing` | フィッシング・なりすまし | 管理者の MFA、問い合わせ窓口の本人確認 | ― | | |
