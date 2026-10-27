# template.md の変更履歴

sync.mjs は `rename:` の行を読んで、記入済みの値を新しい ID へ引き継ぐ。

- v3 (2026-10-27): 21 行を追加し、AI・LLM 機能の層を新設。A2B 攻撃（NICT 2026-10-13）の api.client-analysis・infra.shadow-endpoints、OWASP Top 10 2025・LLM Top 10 2025・Shai-Hulud 等から api.baas-rls / server-action / race-condition / unsafe-consumption / deserialization / cache-poisoning / fail-open、ai.prompt-injection / output-agency / rag、desk.oauth-loopback、ci.workflow-injection / cache-poisoning / malicious-dep、infra.storage-dns / denial-of-wallet、dev.mcp-rules / repo-autorun / dns-rebinding。desk.debug-args の観点に Fuses 全般と OS 権限を足した。
- v2 (2026-10-27): 全行に ID 列を足した(同期のキー)。行の追加・削除はなし。
- v1 (2026-10-27): 初版(vuln-scan/templates に置いていた版)。
