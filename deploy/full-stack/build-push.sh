#!/bin/bash

# 多架构Docker镜像构建和推送脚本 - 支持amd64和arm64
set -e

# 配置变量（优先从环境变量读取）
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_NAME="my-aibox"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BUILDER_NAME="multiarch-builder"

echo "🔧 设置Docker buildx多架构构建器..."
# 创建并使用多架构构建器
docker buildx create --name ${BUILDER_NAME} --use --bootstrap 2>/dev/null || docker buildx use ${BUILDER_NAME}

echo "🔐 登录ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}

echo "🐳 构建并推送多架构镜像 (amd64, arm64)..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} \
  --push \
  .

echo "📋 检查镜像清单..."
docker buildx imagetools inspect ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

echo "✅ 完成!"
echo "📦 多架构镜像地址: ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "🏗️  支持架构: linux/amd64, linux/arm64"
