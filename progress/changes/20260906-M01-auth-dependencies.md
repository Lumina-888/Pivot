# 变更申请：M01 认证依赖 argon2-cffi（及可选 PyJWT）

- **日期**：2026-09-06
- **申请人**：M01 身份、会话与授权会话
- **背景**：SPEC §8.1 / NFR-SEC-004 要求密码使用 Argon2id 或 bcrypt。M01 不允许修改 `api/pyproject.toml`（Owner 为 M03）。当前 `api/pyproject.toml` 只有 SQLAlchemy/Alembic 与测试依赖。
- **原契约**：密码算法已由 SPEC 冻结为 Argon2id/bcrypt；access token 为 JWT（OpenAPI `bearerFormat: JWT`）。有效期秒数仍为 `TBD-P0`，本申请不冻结 TTL。
- **拟变更内容**：
  - 请 M03 在 `api/pyproject.toml` 增加生产依赖 `argon2-cffi`（Argon2id）；
  - 可选：`PyJWT`。M01 当前 access token 使用标准库 HMAC-SHA256 紧凑编码，字段含 `sub/username/role/tv/iat/exp`，待依赖合并后可无行为变化地替换实现；
  - 登录失败阈值、解锁窗口、access/refresh TTL 仍为 `TBD-P0`，M01 只接受注入值，不写默认生产阈值。
- **影响模块**：M03（依赖锁）；M01（消费）；M11（镜像/CI 安装）。
- **兼容方案**：M01 单元测试使用 `TestPasswordHasher`（PBKDF2）注入，不依赖 `argon2-cffi`。`Argon2idHasher` 在缺少该包时失败并指向本文件。Refresh 凭证只以 SHA-256 哈希保存在 RefreshTokenStore，不入库明文。
- **测试 ID**：`test_NFR_SEC_004_argon2id_hasher_uses_expected_prefix`、`test_FR_AUTH_001_*`、`test_FR_AUTH_004_*`。
- **是否触发 ADR**：否（算法已由 SPEC 指定；不改变状态机、权限或检索配置）。
- **审核结果**：待 M03/集成维护者审核。
