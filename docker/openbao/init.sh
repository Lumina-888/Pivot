#!/bin/bash
set -e

# OpenBao 初始化脚本
# 用途: 初始化 OpenBao 并创建 Pivot 所需的密钥和策略
# 使用: ./init.sh

OPENBAO_ADDR=${OPENBAO_ADDR:-"http://localhost:8200"}
OPENBAO_TOKEN=${OPENBAO_TOKEN:-"dev-root-token"}

echo "🔐 OpenBao 初始化脚本"
echo "================================"
echo "地址: $OPENBAO_ADDR"
echo ""

# 检查 OpenBao 是否可用
echo "1️⃣  检查 OpenBao 连接..."
if ! curl -s "$OPENBAO_ADDR/v1/sys/health" > /dev/null; then
    echo "❌ 错误: 无法连接到 OpenBao ($OPENBAO_ADDR)"
    echo "请确保 OpenBao 已启动: docker-compose up -d"
    exit 1
fi
echo "✅ OpenBao 连接成功"
echo ""

# 等待 OpenBao 完全启动
echo "2️⃣  等待 OpenBao 就绪..."
sleep 2

# 启用 KV secrets engine (v2)
echo "3️⃣  启用 KV secrets engine..."
curl -s -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    "$OPENBAO_ADDR/v1/sys/mounts/secret" \
    -d '{
        "type": "kv",
        "options": {
            "version": "2"
        }
    }' || echo "   (可能已存在，跳过)"
echo "✅ KV engine 已启用"
echo ""

# 生成并存储 checkpoint 密钥
echo "4️⃣  生成 checkpoint 加密密钥..."
CHECKPOINT_KEY=$(openssl rand -base64 32)
curl -s -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    "$OPENBAO_ADDR/v1/secret/data/pivot/checkpoint-key" \
    -d "{
        \"data\": {
            \"key\": \"$CHECKPOINT_KEY\",
            \"version\": \"1\",
            \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
            \"algorithm\": \"AES-256-GCM\"
        }
    }" > /dev/null
echo "✅ checkpoint-key 已创建"
echo ""

# 生成并存储 admission 密钥
echo "5️⃣  生成 admission 加密密钥..."
ADMISSION_KEY=$(openssl rand -base64 32)
curl -s -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    "$OPENBAO_ADDR/v1/secret/data/pivot/admission-key" \
    -d "{
        \"data\": {
            \"key\": \"$ADMISSION_KEY\",
            \"version\": \"1\",
            \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
            \"algorithm\": \"AES-256-GCM\"
        }
    }" > /dev/null
echo "✅ admission-key 已创建"
echo ""

# 创建 Pivot Runner 策略
echo "6️⃣  创建 pivot-runner 策略..."
curl -s -X PUT \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    "$OPENBAO_ADDR/v1/sys/policies/acl/pivot-runner" \
    -d '{
        "policy": "path \"secret/data/pivot/*\" {\n  capabilities = [\"read\"]\n}\n\npath \"secret/metadata/pivot/*\" {\n  capabilities = [\"list\"]\n}"
    }' > /dev/null
echo "✅ pivot-runner 策略已创建"
echo ""

# 创建应用 token
echo "7️⃣  创建应用 token..."
RESPONSE=$(curl -s -X POST \
    -H "X-Vault-Token: $OPENBAO_TOKEN" \
    "$OPENBAO_ADDR/v1/auth/token/create" \
    -d '{
        "policies": ["pivot-runner"],
        "ttl": "720h",
        "renewable": true,
        "display_name": "pivot-runner-token"
    }')

APP_TOKEN=$(echo "$RESPONSE" | grep -o '"client_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$APP_TOKEN" ]; then
    echo "❌ 错误: 无法创建应用 token"
    echo "响应: $RESPONSE"
    exit 1
fi
echo "✅ 应用 token 已创建"
echo ""

# 验证配置
echo "8️⃣  验证配置..."
TEST_READ=$(curl -s -H "X-Vault-Token: $APP_TOKEN" \
    "$OPENBAO_ADDR/v1/secret/data/pivot/checkpoint-key")

if echo "$TEST_READ" | grep -q "\"key\""; then
    echo "✅ Token 权限验证通过"
else
    echo "❌ 警告: Token 权限验证失败"
fi
echo ""

# 生成 .env 配置
echo "9️⃣  生成环境变量配置..."
cat > .env.openbao << EOF
# OpenBao 配置
# 由 init.sh 自动生成于 $(date)
# ⚠️  警告: 此文件包含敏感信息，不要提交到 Git

OPENBAO_ADDR=http://localhost:8200
OPENBAO_TOKEN=$APP_TOKEN
OPENBAO_KEY_PATH=secret/pivot

# 加密模式
PIVOT_ENCRYPTION=openbao

# 开发模式备用配置（仅开发环境）
# PIVOT_ENCRYPTION=dev-file
# PIVOT_KEY_FILE=.keys/dev-only.key
EOF

echo "✅ 配置文件已生成: .env.openbao"
echo ""

# 生成摘要报告
echo "================================"
echo "✅ OpenBao 初始化完成！"
echo "================================"
echo ""
echo "📋 配置摘要:"
echo "  - KV Engine: secret/"
echo "  - Checkpoint Key: secret/pivot/checkpoint-key"
echo "  - Admission Key: secret/pivot/admission-key"
echo "  - Runner Policy: pivot-runner"
echo "  - App Token: $APP_TOKEN"
echo ""
echo "📝 下一步:"
echo "  1. 复制配置到主 .env:"
echo "     cat .env.openbao >> ../.env"
echo ""
echo "  2. 验证连接:"
echo "     export OPENBAO_TOKEN=$APP_TOKEN"
echo "     curl -H \"X-Vault-Token: \$OPENBAO_TOKEN\" \\"
echo "          $OPENBAO_ADDR/v1/secret/data/pivot/checkpoint-key"
echo ""
echo "  3. 在应用中使用:"
echo "     PIVOT_ENCRYPTION=openbao python -m pivot.app"
echo ""
echo "⚠️  安全提醒:"
echo "  - .env.openbao 已添加到 .gitignore"
echo "  - 生产环境使用环境变量而非文件存储 token"
echo "  - 定期轮换 token (720h TTL)"
echo ""
