# template.md の変更履歴

sync.mjs は `rename:` の行を読んで、記入済みの値を新しい ID へ引き継ぐ。

- v4 (2026-11-18): 10 行を追加。国内の医療・訪問診療の漏えい事例（2026年: サポート詐欺による遠隔操作、オンライン診療へのリスト型攻撃、保守用 VPN 経由のランサムウェア、委託先 SaaS・業務支援システムの DB 侵害、電子カルテの目的外閲覧、バックアップ HDD の紛失）から api.credential-stuffing / insider-access / bulk-exfil / data-minimization、infra.remote-access / vendor / ransomware / incident-response、dev.support-scam / local-copy。
- v3 (2026-10-27): 21 行を追加し、AI・LLM 機能の層を新設。A2B 攻撃（NICT 2026-10-13）の api.client-analysis・infra.shadow-endpoints、OWASP Top 10 2025・LLM Top 10 2025・Shai-Hulud 等から api.baas-rls / server-action / race-condition / unsafe-consumption / deserialization / cache-poisoning / fail-open、ai.prompt-injection / output-agency / rag、desk.oauth-loopback、ci.workflow-injection / cache-poisoning / malicious-dep、infra.storage-dns / denial-of-wallet、dev.mcp-rules / repo-autorun / dns-rebinding。desk.debug-args の観点に Fuses 全般と OS 権限を足した。
- v2 (2026-10-27): 全行に ID 列を足した(同期のキー)。行の追加・削除はなし。
- v1 (2026-10-27): 初版(vuln-scan/templates に置いていた版)。
