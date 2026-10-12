# OpenBao 集成指南

> **版本**: 1.0  
> **更新**: 2026-10-12  
> **用途**: 为 Pivot Agent 提供密钥管理服务

---

## 1. 什么是 OpenBao？

OpenBao 是 HashiCorp Vault 的开源分支，提供：
- 密钥存储和管理
- 细粒度访问控制
- 审计日志
- 密钥轮换

**为什么选择 OpenBao？**
- ✅ 开源，避免供应商锁定
- ✅ 功能完整，兼容 Vault
- ✅ 社区活跃
- ✅ 自托管，完全控制

---

## 2. 快速开始

### 2.1 启动 OpenBao

```bash
cd docker/openbao
docker-compose up -d
```

**验证启动**:
```bash
curl http://localhost:8200/v1/sys/health
```

应该返回 JSON，包含 `"initialized": true`

### 2.2 初始化配置

```bash
cd docker/openbao
./init.sh
```

脚本会自动：
1. 启用 KV secrets engine
2. 生成 checkpoint 加密密钥
3. 生成 admission 加密密钥
4. 创建 pivot-runner 策略
5. 创建应用 token
6. 生成 `.env.openbao` 配置文件

### 2.3 配置应用

```bash
# 将配置添加到主 .env
cat docker/openbao/.env.openbao >> .env

# 或手动添加
echo "PIVOT_ENCRYPTION=openbao" >> .env
echo "OPENBAO_ADDR=http://localhost:8200" >> .env
echo "OPENBAO_TOKEN=<your-token>" >> .env
```

---

## 3. 架构设计

### 3.1 密钥层次结构

```
secret/pivot/
├── checkpoint-key      # Checkpoint State 加密
│   ├── key            # AES-256 密钥（Base64）
│   ├── version        # 密钥版本号
│   └── algorithm      # 加密算法
└── admission-key       # ResumeAdmission answer 加密
    ├── key
    ├── version
    └── algorithm
```

### 3.2 访问控制

**pivot-runner 策略**:
```hcl
# 读取 Pivot 密钥
path "secret/data/pivot/*" {
  capabilities = ["read"]
}

# 列出 Pivot 密钥元数据
path "secret/metadata/pivot/*" {
  capabilities = ["list"]
}
```

**root token**:
- 仅用于初始化和管理
- 不用于应用运行时
- 生产环境应该吊销或严格限制

---

## 4. 应用集成

### 4.1 Python 客户端

```python
# api/src/pivot/crypto/openbao.py

import hvac
from typing import Optional

class OpenBaoClient:
    def __init__(self, addr: str, token: str):
        self.client = hvac.Client(url=addr, token=token)
        if not self.client.is_authenticated():
            raise ValueError("OpenBao authentication failed")
    
    def get_key(self, path: str, version: Optional[int] = None) -> dict:
        """读取密钥
        
        Args:
            path: 密钥路径，如 "pivot/checkpoint-key"
            version: 密钥版本，None 表示最新版本
        
        Returns:
            {"key": "...", "version": "1", "algorithm": "AES-256-GCM"}
        """
        mount_point = "secret"
        secret_path = f"{mount_point}/data/{path}"
        
        params = {}
        if version:
            params["version"] = version
        
        response = self.client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount_point,
            **params
        )
        
        return response["data"]["data"]
    
    def list_keys(self, path: str = "pivot") -> list[str]:
        """列出路径下的密钥"""
        response = self.client.secrets.kv.v2.list_secrets(
            path=path,
            mount_point="secret"
        )
        return response["data"]["keys"]
```

### 4.2 加密服务

```python
# api/src/pivot/crypto/encryption.py

import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .openbao import OpenBaoClient

class EncryptionService:
    def __init__(self, openbao: OpenBaoClient):
        self.openbao = openbao
        self._key_cache = {}
    
    def encrypt(self, plaintext: str, key_path: str = "pivot/checkpoint-key") -> dict:
        """加密数据
        
        Returns:
            {
                "ciphertext": "base64...",
                "nonce": "base64...",
                "key_ref": "pivot/checkpoint-key",
                "key_version": 1
            }
        """
        # 获取密钥
        key_data = self._get_cached_key(key_path)
        key = base64.b64decode(key_data["key"])
        
        # AES-256-GCM 加密
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "key_ref": key_path,
            "key_version": int(key_data["version"])
        }
    
    def decrypt(self, encrypted: dict) -> str:
        """解密数据"""
        # 获取密钥（指定版本）
        key_data = self._get_cached_key(
            encrypted["key_ref"],
            version=encrypted["key_version"]
        )
        key = base64.b64decode(key_data["key"])
        
        # 解密
        aesgcm = AESGCM(key)
        nonce = base64.b64decode(encrypted["nonce"])
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
    
    def _get_cached_key(self, path: str, version: Optional[int] = None) -> dict:
        """缓存密钥（避免频繁请求 OpenBao）"""
        cache_key = f"{path}:{version or 'latest'}"
        
        if cache_key not in self._key_cache:
            self._key_cache[cache_key] = self.openbao.get_key(path, version)
        
        return self._key_cache[cache_key]
```

### 4.3 配置加载

```python
# api/src/pivot/config.py

from enum import Enum
from pydantic_settings import BaseSettings

class EncryptionMode(str, Enum):
    DISABLED = "disabled"      # 不加密（仅测试）
    DEV_FILE = "dev-file"      # 文件密钥（开发）
    OPENBAO = "openbao"        # OpenBao（生产）
    AWS_KMS = "aws-kms"        # AWS KMS（云端）

class Settings(BaseSettings):
    # 加密配置
    encryption_mode: EncryptionMode = EncryptionMode.DISABLED
    
    # OpenBao 配置
    openbao_addr: str = "http://localhost:8200"
    openbao_token: str = ""
    openbao_key_path: str = "secret/pivot"
    
    # 开发模式配置
    dev_key_file: str = ".keys/dev-only.key"
    
    def validate_agent_config(self):
        """验证 Agent 模式配置"""
        if not self.is_postgres_configured():
            raise ValueError("Agent mode requires PostgreSQL")
        
        if self.encryption_mode == EncryptionMode.DISABLED:
            raise ValueError("Agent mode requires encryption")
        
        if self.encryption_mode == EncryptionMode.DEV_FILE:
            if self.is_production():
                raise ValueError("dev-file encryption not allowed in production")
        
        if self.encryption_mode == EncryptionMode.OPENBAO:
            if not self.openbao_addr or not self.openbao_token:
                raise ValueError("OpenBao configuration incomplete")
```

---

## 5. 密钥轮换

### 5.1 创建新版本密钥

```bash
# 生成新密钥
NEW_KEY=$(openssl rand -base64 32)

# 创建版本 2
curl -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    http://localhost:8200/v1/secret/data/pivot/checkpoint-key \
    -d "{
        \"data\": {
            \"key\": \"$NEW_KEY\",
            \"version\": \"2\",
            \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }
    }"
```

### 5.2 应用迁移策略

```python
# 新 checkpoint 使用 v2 加密
encrypted = encryption.encrypt(state, key_path="pivot/checkpoint-key")
# -> {"key_version": 2, ...}

# 旧 checkpoint 仍可用 v1 解密
decrypted = encryption.decrypt(old_encrypted)
# -> 自动使用 old_encrypted["key_version"] = 1
```

### 5.3 清理旧版本

```bash
# 列出所有版本
curl -H "X-Vault-Token: $OPENBAO_TOKEN" \
    http://localhost:8200/v1/secret/metadata/pivot/checkpoint-key

# 删除版本 1（确保无数据使用后）
curl -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    http://localhost:8200/v1/secret/delete/pivot/checkpoint-key \
    -d '{"versions": [1]}'
```

---

## 6. 故障排查

### 6.1 连接失败

**症状**: `connection refused`

**检查**:
```bash
# 1. 检查 Docker 容器
docker ps | grep openbao

# 2. 检查端口
netstat -tulpn | grep 8200

# 3. 检查日志
docker logs pivot-openbao
```

### 6.2 认证失败

**症状**: `permission denied`

**检查**:
```bash
# 验证 token
curl -H "X-Vault-Token: $OPENBAO_TOKEN" \
    http://localhost:8200/v1/auth/token/lookup-self

# 重新生成 token
cd docker/openbao
./init.sh
```

### 6.3 密钥不存在

**症状**: `secret not found`

**检查**:
```bash
# 列出密钥
curl -H "X-Vault-Token: $OPENBAO_TOKEN" \
    http://localhost:8200/v1/secret/metadata/pivot?list=true

# 重新初始化
cd docker/openbao
./init.sh
```

---

## 7. 生产部署

### 7.1 TLS 配置

```json
// docker/openbao/config/config.json (生产)
{
  "listener": {
    "tcp": {
      "address": "0.0.0.0:8200",
      "tls_cert_file": "/openbao/tls/cert.pem",
      "tls_key_file": "/openbao/tls/key.pem",
      "tls_disable": false
    }
  }
}
```

### 7.2 持久化存储

**开发**: File backend
```json
"storage": {
  "file": {
    "path": "/openbao/file"
  }
}
```

**生产**: PostgreSQL backend
```json
"storage": {
  "postgresql": {
    "connection_url": "postgres://user:pass@localhost/openbao",
    "ha_enabled": "true"
  }
}
```

### 7.3 高可用

```yaml
# docker-compose.yml (HA)
services:
  openbao-1:
    image: openbao/openbao:2.0.0
    # ... 配置 PostgreSQL backend
  
  openbao-2:
    image: openbao/openbao:2.0.0
    # ... 同样的 backend，自动 HA
```

---

## 8. 安全检查清单

- [ ] ✅ Root token 已限制使用
- [ ] ✅ 应用使用最小权限 token (pivot-runner)
- [ ] ✅ Token TTL 配置合理 (720h)
- [ ] ✅ TLS 已启用 (生产)
- [ ] ✅ 审计日志已启用
- [ ] ✅ 密钥轮换计划已制定
- [ ] ✅ 备份策略已实施
- [ ] ✅ .env 文件不提交到 Git
- [ ] ✅ Docker 卷权限正确

---

## 9. 参考资源

- [OpenBao 官方文档](https://openbao.org/docs/)
- [KV Secrets Engine v2](https://openbao.org/docs/secrets/kv/kv-v2/)
- [HVAC Python Client](https://hvac.readthedocs.io/)
- [Vault 迁移指南](https://openbao.org/docs/migration/)

---

**更新日志**:
- 2026-10-12: 初始版本，支持开发和生产配置
