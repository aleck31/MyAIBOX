#!/bin/bash

# AgentCore Runtime 部署脚本
# 将 Agent 后端部署到 AWS Bedrock AgentCore Runtime
# 所有环境配置通过 --env 注入，不在镜像中硬编码
set -e

# ── 基础配置（可通过环境变量覆盖）────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
BEDROCK_REGION="${BEDROCK_REGION:-us-west-2}"

# DynamoDB 表名
SETTING_TABLE="${SETTING_TABLE:-aibox_setting}"
SESSION_TABLE="${SESSION_TABLE:-aibox_session}"

# Secrets Manager 中的 Secret 名称（非真实密钥）
GEMINI_SECRET_ID="${GEMINI_SECRET_ID:-dev_gemini_api}"
OPENAI_SECRET_ID="${OPENAI_SECRET_ID:-dev_openai_api}"

# ── 部署 ──────────────────────────────────────────────────────────────────────
echo "Deploying MyAIBOX Agent to AgentCore Runtime..."
echo "  AWS_REGION:       ${AWS_REGION}"
echo "  BEDROCK_REGION:   ${BEDROCK_REGION}"
echo "  SETTING_TABLE:    ${SETTING_TABLE}"
echo "  SESSION_TABLE:    ${SESSION_TABLE}"
echo "  GEMINI_SECRET_ID: ${GEMINI_SECRET_ID}"
echo "  OPENAI_SECRET_ID: ${OPENAI_SECRET_ID}"
echo ""

.venv/bin/agentcore deploy \
  --env AWS_REGION="${AWS_REGION}" \
  --env AWS_DEFAULT_REGION="${AWS_REGION}" \
  --env BEDROCK_REGION="${BEDROCK_REGION}" \
  --env SETTING_TABLE="${SETTING_TABLE}" \
  --env SESSION_TABLE="${SESSION_TABLE}" \
  --env GEMINI_SECRET_ID="${GEMINI_SECRET_ID}" \
  --env OPENAI_SECRET_ID="${OPENAI_SECRET_ID}" \
  --env LOG_TO_FILE="false"

echo "Deploy complete."
