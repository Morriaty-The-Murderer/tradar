# Tradar Fixtures

这些 fixture 是脱敏后的结构样本，只用于锁定 connector 契约。

脱敏规则：

- 用户目录统一写成 `<USER_HOME>`。
- 项目名统一写成 `<REPO_NAME>`。
- session 正文只保留短句结构，不保留真实私人内容。
- token、key、cookie、账号信息统一替换为 `<SECRET_REDACTED>`。
- 工具输出只保留结构和边界条件，不保留真实命令长输出。

每个 connector 至少保留：

- happy path
- missing optional fields
- parse warning / parse error 边界样本
