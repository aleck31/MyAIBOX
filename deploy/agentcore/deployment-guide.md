# AgentCore Runtime Deployment Guide

This guide covers deploying the MyAIBOX Agent service to AWS Bedrock AgentCore Runtime for serverless execution.

## Overview

AgentCore Runtime provides:
- **Serverless execution** - No infrastructure management
- **Up to 8 hours** execution time (vs Lambda's 15 minutes)
- **Session isolation** - Each request runs in isolated environment
- **Built-in observability** - CloudWatch integration
- **Streaming support** - Server-Sent Events (SSE) for real-time responses

## Prerequisites

1. AWS Account with Bedrock AgentCore access
2. AWS CLI configured with appropriate credentials
3. Python 3.12+
4. uv package manager

## Installation

```bash
# Install dependencies
uv sync

# Verify bedrock-agentcore is installed
uv run python -c "import bedrock_agentcore; print(bedrock_agentcore.__version__)"
```

## Project Structure

```
my-aibox/
├── agentcore_app.py      # AgentCore entry point
├── genai/
│   └── agents/
│       └── provider.py   # Core agent logic (reused)
└── pyproject.toml        # Dependencies include bedrock-agentcore
```

## Entry Point: agentcore_app.py

The `agentcore_app.py` file wraps the existing `AgentProvider` for AgentCore deployment:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from genai.agents.provider import AgentProvider

app = BedrockAgentCoreApp()

@app.entrypoint
async def handle_request(request):
    """
    Async entry point supporting both streaming and non-streaming modes.
    Returns async generator for streaming, dict for non-streaming.
    """
    if request.get('stream', False):
        # Return async generator for SSE streaming
        async def generate():
            async for chunk in stream_agent_async(...):
                yield chunk
        return generate()
    else:
        # Return full response
        return await run_agent_async(...)
```

## Request Format

### Invoke Agent (Non-Streaming)

```json
{
    "action": "invoke",
    "prompt": "What is the weather in Tokyo?",
    "model_id": "global.anthropic.claude-sonnet-4-6",
    "system_prompt": "You are a helpful assistant.",
    "history": [],
    "stream": false,
    "tool_config": {
        "enabled": true,
        "legacy_tools": ["get_weather"],
        "strands_tools_enabled": true,
        "mcp_tools_enabled": false
    }
}
```

### Invoke Agent (Streaming)

```json
{
    "prompt": "What is the weather in Tokyo?",
    "stream": true
}
```

### Health Check

```json
{
    "action": "health"
}
```

## Response Format

### Non-Streaming Response

```json
{
    "response": "The weather in Tokyo is...",
    "tool_calls": [
        {
            "name": "get_weather",
            "params": {"location": "Tokyo"},
            "status": "completed",
            "result": "..."
        }
    ],
    "metadata": {},
    "status": "success"
}
```

### Streaming Response (SSE)

当 `stream: true` 时，返回 Server-Sent Events 格式：

```
data: {"text": ""}
data: {"tool_use": {"name": "current_time", "status": "running", "tool_use_id": "..."}}
data: {"text": "The current time is "}
data: {"text": "2026-01-11..."}
data: {"tool_use": {"name": "current_time", "status": "completed", "result": "...", "tool_use_id": "..."}}
data: {"text": "."}
data: {"status": "complete", "event": "done"}
```

**Chunk 类型说明**：

| 字段 | 说明 |
|------|------|
| `text` | 文本内容片段 |
| `thinking` | 模型思考过程 (Claude extended thinking) |
| `tool_use` | 工具调用事件，包含 `name`, `params`, `status`, `result` |
| `metadata` | 元数据信息 |
| `status: complete` | 流结束标记 |
| `status: error` | 错误信息 |

## Local Testing

```bash
# Test non-streaming mode
uv run python agentcore_app.py

# Test streaming mode
uv run python agentcore_app.py --stream

# Start local server
uv run python agentcore_app.py --server
```

## Deploy to AgentCore

### Using CLI

```bash
# Configure entry point (first time only)
uv run agentcore configure -e agentcore_app.py

# Deploy (uses CodeBuild for ARM64 container)
uv run agentcore deploy

# Test non-streaming
uv run agentcore invoke '{"prompt": "Hello!"}'

# Test streaming
uv run agentcore invoke '{"prompt": "Count 1 to 5", "stream": true}'

# Test with tools
uv run agentcore invoke '{"prompt": "What time is it?", "stream": true}'

# View logs
uv run agentcore logs

# Destroy deployment
uv run agentcore destroy
```

## Environment Variables

容器运行时所需的环境变量在 Dockerfile 中配置（不使用 `.env` 文件，`.dockerignore` 将其排除）：

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `ap-southeast-1` | AWS 区域 |
| `AWS_DEFAULT_REGION` | `ap-southeast-1` | boto3 默认区域 |
| `BEDROCK_REGION` | `us-west-2` | Bedrock 模型调用区域 |
| `SETTING_TABLE` | `aibox_setting` | DynamoDB 配置表名 |
| `SESSION_TABLE` | `aibox_session` | DynamoDB 会话表名 |
| `GEMINI_SECRET_ID` | `dev_gemini_api` | Secrets Manager 中 Gemini API Key 的 secret ID |
| `OPENAI_SECRET_ID` | `dev_openai_api` | Secrets Manager 中 OpenAI API Key 的 secret ID |

> **注意**: 修改 Dockerfile 中的环境变量后需重新执行 `agentcore deploy` 才能生效。

## Model Selection

The entry point automatically selects a model that supports:
1. Tool use capability
2. Streaming capability

Default fallback: `global.anthropic.claude-sonnet-4-6`

To specify a model explicitly:

```json
{
    "prompt": "...",
    "model_id": "your-preferred-model-id"
}
```

## Available Tools

### Legacy Tools
- `get_weather` - Weather information
- `search_internet` - Web search
- `search_wikipedia` - Wikipedia search
- `get_text_from_url` - URL content extraction
- `generate_image` - Image generation

### Strands Built-in Tools
- `current_time` - Current time
- `calculator` - Math calculations
- `http_request` - HTTP requests
- `sleep` - Delay execution
- `speak` - Text-to-speech

## Streaming Implementation

### HTTP Streaming (SSE)

AgentCore 通过 Server-Sent Events 支持 HTTP 流式响应：

```python
@app.entrypoint
async def handle_request(request):
    if request.get('stream'):
        # 返回 async generator，AgentCore 自动转为 SSE
        async def generate():
            async for chunk in stream_agent_async(...):
                yield chunk  # 每个 chunk 变成 "data: {...}\n\n"
        return generate()
```

**工作原理**：
1. `@app.entrypoint` 检测到返回 async generator
2. 自动包装为 `StreamingResponse(media_type="text/event-stream")`
3. 每个 yield 的对象自动 JSON 序列化并格式化为 SSE

### WebSocket Streaming

AgentCore 也支持 WebSocket 双向通信：

```python
@app.websocket
async def ws_handler(websocket, context):
    await websocket.accept()

    # 接收请求
    data = await websocket.receive_json()

    # 流式发送响应
    async for chunk in stream_agent_async(data['prompt']):
        await websocket.send_json(chunk)

    await websocket.close()
```

**客户端连接**：

```python
from bedrock_agentcore.runtime import AgentCoreRuntimeClient

client = AgentCoreRuntimeClient(region="ap-southeast-1")
ws_url, headers = client.generate_ws_connection(
    runtime_arn="arn:aws:bedrock-agentcore:ap-southeast-1:xxx:runtime/my_aibox_agent-xxx"
)

# 使用 websockets 库连接
import websockets
async with websockets.connect(ws_url, extra_headers=headers) as ws:
    await ws.send(json.dumps({"prompt": "Hello"}))
    async for message in ws:
        print(json.loads(message))
```

## Comparison: Lambda vs AgentCore Runtime

| Feature | Lambda | AgentCore Runtime |
|---------|--------|-------------------|
| Max execution | 15 min | 8 hours |
| Streaming | Response streaming only | SSE + WebSocket |
| Memory management | Manual | Built-in Memory component |
| Tool registration | Manual | Gateway auto-conversion |
| Session isolation | DIY | Native support |
| Observability | CloudWatch | Built-in + CloudWatch |

## Container Build Notes

### Package Management

AgentCore 使用 CodeBuild 构建 ARM64 容器镜像。**推荐使用 pip 而非 uv**：

| 方式 | 问题 |
|------|------|
| `uv sync` | 默认安装到 `.venv/`，运行时找不到包 |
| `pip install` | 安装到系统 Python，无问题 |

如需使用 uv：
```dockerfile
# 方法1: 强制系统安装
RUN uv pip install --system -r requirements.txt

# 方法2: 导出后用 pip
RUN uv export --no-hashes > requirements.txt && pip install -r requirements.txt
```

### 依赖文件维护

项目使用独立的 `requirements-agentcore.txt` 管理 AgentCore 容器依赖：

```
# requirements-agentcore.txt
strands-agents
strands-agents-tools
boto3
bedrock-agentcore
python-dotenv
# ... 其他依赖
```

> **注意**: 更新 `pyproject.toml` 时，记得同步更新 `requirements-agentcore.txt`

### Dockerfile 最佳实践

参考 `.bedrock_agentcore/my_aibox_agent/Dockerfile`：

```dockerfile
FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /app

# 使用 pip 安装依赖
COPY requirements-agentcore.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir aws-opentelemetry-distro==0.12.2

# 关键环境变量（.env 文件被 .dockerignore 排除，必须在此设置）
ENV AWS_REGION=ap-southeast-1 \
    AWS_DEFAULT_REGION=ap-southeast-1 \
    PYTHONUNBUFFERED=1 \
    LOG_TO_FILE=false \
    SETTING_TABLE=aibox_setting \
    SESSION_TABLE=aibox_session \
    BEDROCK_REGION=us-west-2 \
    GEMINI_SECRET_ID=dev_gemini_api \
    OPENAI_SECRET_ID=dev_openai_api

COPY . .

# 非 root 用户运行
RUN useradd -m -u 1000 bedrock_agentcore && \
    mkdir -p /app/logs /app/tmp && \
    chown -R bedrock_agentcore:bedrock_agentcore /app

USER bedrock_agentcore
EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "-m", "agentcore_app"]
```

## Authentication

AgentCore Runtime 支持多种鉴权方式，默认要求 AWS SigV4 签名。

### 默认鉴权：AWS SigV4

即使 `network_mode: PUBLIC`，调用 AgentCore 端点仍需：
1. 有效的 AWS 凭证
2. `bedrock-agentcore:InvokeAgent` IAM 权限

```bash
# 无凭证调用会返回 403
curl -X POST "https://bedrock-agentcore.ap-southeast-1.amazonaws.com/..." \
  -d '{"action": "health"}'
# {"message":"Missing Authentication Token"}
```

### 鉴权选项一览

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **AWS SigV4** | 默认启用，需 AWS 凭证 | 后端服务间调用 |
| **AWS JWT** | 为用户生成短期 JWT | 前端直接调用 |
| **OAuth** | 集成 Cognito/第三方 IdP | 用户登录后调用 |
| **API Key** | 简单的 Key 验证 | 简单集成场景 |
| **Custom Authorizer** | Lambda 自定义鉴权 | 复杂鉴权逻辑 |

### 启用 OAuth (推荐用于 Web 应用)

```bash
# 配置 OAuth
uv run agentcore configure --oauth-enabled

# 重新部署
uv run agentcore deploy
```

配置文件 `.bedrock_agentcore.yaml` 中会添加：

```yaml
oauth_configuration:
  enabled: true
  provider: cognito  # 或其他 IdP
  issuer_url: https://cognito-idp.ap-southeast-1.amazonaws.com/xxx
  audiences: ["your-client-id"]
```

### 启用 JWT

```bash
uv run agentcore configure --jwt-enabled
```

配置：

```yaml
aws_jwt:
  enabled: true
  audiences: ["your-audience"]
  signing_algorithm: ES384
  issuer_url: https://your-issuer.com
  duration_seconds: 300
```

### 客户端调用示例

**使用 AWS 凭证 (SigV4)**：

```python
from bedrock_agentcore.runtime import AgentCoreRuntimeClient

client = AgentCoreRuntimeClient(region="ap-southeast-1")
ws_url, headers = client.generate_ws_connection(runtime_arn)
# headers 包含 SigV4 签名
```

**使用 OAuth Bearer Token**：

```python
ws_url, headers = client.generate_ws_connection_oauth(
    runtime_arn=runtime_arn,
    bearer_token="eyJhbGciOiJSUzI1NiIs..."
)
```

**使用预签名 URL (前端友好)**：

```python
# 生成 5 分钟有效的预签名 URL
presigned_url = client.generate_presigned_url(
    runtime_arn=runtime_arn,
    expires=300
)
# 前端可直接使用此 URL 连接 WebSocket，无需管理 AWS 凭证
```

### 当前部署状态

查看 `.bedrock_agentcore.yaml`：

```yaml
network_mode: PUBLIC           # 网络可达
aws_jwt.enabled: false         # JWT 未启用
oauth_configuration: null      # OAuth 未启用
api_key_env_var_name: null     # API Key 未启用
```

> **安全提示**：默认配置下，只有拥有 AWS 账号凭证且有相应 IAM 权限的调用者才能访问 AgentCore Runtime。

## Troubleshooting

### 1. setuptools 包发现错误

**错误**: `Multiple top-level packages discovered in a flat-layout`

**原因**: 项目根目录有多个 Python 包目录，setuptools 无法自动识别

**解决**: 在 `pyproject.toml` 中显式指定包：

```toml
[tool.setuptools.packages.find]
include = ["core*", "genai*", "webui*", "common*", "utils*"]
exclude = ["tests*", "devguide*", "logs*", "tmp*", "assets*"]
```

### 2. 运行时 ModuleNotFoundError

**错误**: `ModuleNotFoundError: No module named 'botocore'` 或其他模块

**原因**:
- `uv sync` 安装到虚拟环境而非系统 Python
- `requirements.txt` 缺少依赖

**解决**:
1. 改用 `pip install -r requirements.txt`
2. 确保 `requirements-agentcore.txt` 包含所有依赖（包括间接依赖如 `python-dotenv`）

### 3. 日志文件权限错误

**错误**: `PermissionError: [Errno 13] Permission denied: '/app/logs/app.log'`

**原因**: 容器以非 root 用户运行，日志目录权限不足

**解决**: 设置环境变量禁用文件日志：
```dockerfile
ENV LOG_TO_FILE=false
```

### 4. DynamoDB AccessDeniedException

**错误**: `AccessDeniedException: User is not authorized to perform: dynamodb:GetItem`

**原因**: AgentCore 自动创建的 IAM Role 没有 DynamoDB 权限

**解决**: 为 Role 添加内联策略：

```bash
# 查找 Role 名称
aws iam list-roles --query "Roles[?contains(RoleName, 'AgentCore')].RoleName"

# 添加 DynamoDB 权限
aws iam put-role-policy \
    --role-name AmazonBedrockAgentCoreSDKRuntime-ap-southeast-1-XXXXXX \
    --policy-name DynamoDBAccess \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/*"
        }]
    }'
```

> **IAM Role 说明**: Role `AmazonBedrockAgentCoreSDKRuntime-<region>-<hash>` 在首次 `agentcore deploy` 时自动创建，可在 IAM Console 查看和修改权限。

### 5. Gemini / OpenAI API Key 获取失败

**错误**: `Gemini API key not configured` 或 `Error: Gemini API key not configured`

**原因**: AgentCore Runtime 的 IAM Role 没有 Secrets Manager 权限

**解决**: 为 Role 添加 Secrets Manager 权限：

```bash
aws iam put-role-policy \
    --role-name AmazonBedrockAgentCoreSDKRuntime-ap-southeast-1-XXXXXX \
    --policy-name SecretsManagerAccess \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": "arn:aws:secretsmanager:<region>:<account-id>:secret:dev_*"
        }]
    }'
```

> 调整 `Resource` 中的 secret 前缀以匹配实际 secret 命名规则。

### 6. __main__ 测试代码意外执行

**错误**: 每次 invoke 都执行测试代码

**原因**: `if __name__ == "__main__"` 块在容器中也会执行

**解决**: 添加环境变量检查：

```python
if __name__ == "__main__":
    import os
    if not os.environ.get("AWS_EXECUTION_ENV"):
        # 仅本地测试时执行
        test_request = {"prompt": "Hello"}
        result = handle_request(test_request)
        print(result)
    else:
        app.run()
```

### 6. Model doesn't support tool use in streaming mode

**错误**: 某些模型不支持流式工具调用

**解决**:
1. 使用兼容模型 (Claude 3.x)
2. 或禁用工具: `{"tool_config": {"enabled": false}}`

### 7. Cold start latency

AgentCore 容器可能有冷启动延迟。生产环境建议:
- 使用 provisioned concurrency
- 或定期 health check 保持热启动

## Next Steps

1. **AgentCore Memory** - Replace DynamoDB session with built-in Memory
2. **AgentCore Gateway** - Register tools via Gateway for easier management
3. **AgentCore Identity** - Use built-in identity management

See [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/) for more details.
