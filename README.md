# MyAIBOX

MyAIBOX( AI百宝箱) is a comprehensive Gen-AI application suite built with FastAPI and Gradio. It features a user-friendly interface that provides access to various AI capabilities, including AI Agent, multimodal chat, text processing，summarization, image and document recognition, code generation, and image creation tools.

## Overview
The application integrates multiple GenAI models, with secure authentication via Amazon Cognito and session management. 
It provides a modular architecture that makes it easy to add new features and AI models.

Its user-friendly Gradio-based web interface provides an intuitive experience.

🎉 **What's New in v2.1**
- **AgentCore Runtime**: Assistant module can now run as serverless AI Agent on AWS Bedrock AgentCore Runtime (up to 8 hours execution, SSE streaming)
- **Multi-provider Agent**: Agent supports Bedrock, Gemini, and OpenAI models via Strands SDK

**v2.0**
- Optimized performance and reliability
- Enhanced Settings & Configuration
- Improved session management
- Integrated image generation directly in the chatbot
- Improved chat history management with session loading
- Optimized token usage by limiting context window
- Enhanced multimodal message handling with descriptive placeholders
- Added BedrockInvoke provider for image/video generation
- **Unified Tool System**: Simplified tool configuration with 83% faster response times
- **MCP Integration**: Full Model Context Protocol support with optimized architecture

## Features

* **Multimodal Chatbot** 🤖
  - Bedrock-powered agentic AI assistant with streaming responses
  - AI Chatbot with different personality profiles
  - Context-aware conversations
  - Tool use (function calling) integration
  - Seamless handling of generated content
  - Support for text, images, and document inputs
  - Supported formats:
    * Images: jpg/jpeg, png, gif, webp
    * Documents: pdf, csv, doc, docx, xls, xlsx, txt, md
    * Video: mp4, webm, mov, etc.

* **Text Processing** 📝
  - Proofreading: Grammar and spelling checks
  - Text rewriting with different styles
  - Text reduction for conciseness
  - Text expansion for detail enhancement
  - Document and text summarization
  - Multi-language support

* **Vision Recognition** 👀
  - Image analysis and description
  - Document understanding (PDF support)
  - Multi-model support (Claude/Gemini)
  - Camera and clipboard input support

* **Advanced Features**
  - **Asking** 🧠: Provide responses with comprehensive thinking
  - **Coding** 💻: Code generation and analysis
  - **Draw** 🎨: AI-powered image generation
  - **Settings** ⚙️: Customizable configurations

## Screenshots

### Main Interface
![my-aibox](/assets/screenshot.png "Web UI")

### Multimodal Chatbot
![my-aibox](/assets/screenshot_chatbot.png "Multimodal Chatbot")

### Vision Recognition
![my-aibox](/assets/screenshot_vision.png "Vision Recognition")

## Technical Features

* **Service Architecture**
  - Layered design with base service abstraction:
    * BaseService: Common session and LLM provider management
    * Specialized services for chat, drawing, and general content
    * Unified service factory with efficient instantiation
  - Modular session management:
    * Standardized session data structures
    * Pluggable storage backends (DynamoDB implementation)
    * Efficient caching with TTL-based cleanup
    * Session metadata for model and context tracking

* **LLM Integration**
  - Flexible provider management:
    * Unified LLM configuration handling
    * Provider-specific parameter optimization
    * Efficient provider caching and reuse
  - Advanced streaming capabilities:
    * Real-time response streaming
    * Multimodal content support
    * Tool use (function calling) integration with extensible registry
    * Optimized content handling and normalization

## Project Structure

The project follows a clean, layered architecture:

```
my-aibox/
├── app.py                    # Main application entry point
├── core/                     # Core components
│   ├── config.py                 # Configuration settings
│   ├── module_config.py          # Module configuration
│   ├── service/                  # Service layer
│   │   ├── agent_service.py          # AI Agent service (local or AgentCore)
│   │   ├── gen_service.py            # General content generation
│   │   ├── chat_service.py           # Chat service
│   │   ├── draw_service.py           # Image generation service
│   │   └── service_factory.py        # Service creation factory
│   └── session/                  # Session management
│       ├── models.py                 # Session data models
│       └── store.py                  # DynamoDB-based session storage
├── common/                   # Common modules
│   ├── auth.py                   # Cognito authentication
│   └── logger.py                 # Logging configuration
├── genai/                    # GenAI integration
│   ├── models/                   # LLM model implementations
│   │   ├── providers/                # BedrockConverse, Gemini, OpenAI providers
│   │   └── model_manager.py          # Model management
│   ├── agents/                   # AI Agent implementations
│   │   ├── provider.py               # Strands Agent (local execution)
│   │   └── agentcore_client.py       # AgentCore Runtime client (remote)
│   └── tools/                    # Tool implementations
│       ├── legacy/                   # Legacy tools (weather, search, etc.)
│       ├── mcp/                      # MCP tools
│       └── provider.py               # Unified tool provider
├── utils/                    # Utility functions
├── webui/                    # Gradio Web UI
│   ├── modules/                  # Feature modules
│   │   ├── assistant/                # AI Assistant (uses AgentService)
│   │   ├── persona/                  # Chatbot with personality profiles
│   │   ├── text/                     # Text processing
│   │   ├── summary/                  # Text summarization
│   │   ├── vision/                   # Image analysis
│   │   ├── asking/                   # Q&A with reasoning
│   │   ├── coding/                   # Code generation
│   │   └── draw/                     # Image generation
│   └── settings/                 # Settings UI
├── agentcore_app.py          # AgentCore Runtime entry point
└── requirements-agentcore.txt # Dependencies for AgentCore container
```

## Tool System

MyAIBOX features a unified tool system supporting three types of tools with optimized performance and easy configuration.

### 🎯 Tool Types

| Tool Type | Configuration | Use Case | Examples |
|-----------|---------------|----------|----------|
| **Legacy Tools** | Module Configuration | Simple functions, module-specific | `get_weather`, `search_wikipedia` |
| **Strands Tools** | Always enabled | Basic functions, globally available | `calculator`, `current_time` |
| **MCP Tools** | Tool Management | Complex functions, external services | `exa-server`, `core-mcp-server` |

### 🚀 Quick Configuration

#### Configure Legacy Tools (Module Level)
```
Settings → Module Configuration → Assistant Module Settings
Select tools: ☑️ get_weather ☑️ generate_image
Click 💾 Save
```

#### Configure MCP Tools (Global Level)
```
Settings → Tool Management
Click ➕ Add New MCP Server
Fill server info, click ➕ Add Server
```

#### Strands Tools (Auto-enabled)
Strands build-in tools: `current_time`, `calculator`, `http_request`, `sleep`, `speak`

### 📊 Tool Configuration Format

```python
tool_config = {
    'enabled': True,  # Master switch for debugging
    'legacy_tools': ['get_weather', 'generate_image'],
    'mcp_tools_enabled': True,
    'strands_tools_enabled': True,
}
```

### 🔧 Adding MCP Servers

**HTTP Server:**
```json
{
    "name": "my-api-server",
    "type": "http", 
    "url": "https://api.example.com/mcp"
}
```

**Local Server:**
```json
{
    "name": "local-tool",
    "type": "stdio",
    "command": "uvx",
    "args": ["my-package@latest"]
}
```

## Setup

1. Install dependencies:
```bash
# Install uv if you don't have it already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies using uv
uv sync
```

2. Configure AWS credentials:
```bash
aws configure
```

3. Configure environment file:
```bash
cp .env.example .env
```

4. Update environment with your settings:
- AWS region and Cognito user pool details
- DynamoDB table names
- LLM provider API keys (stored in AWS Secrets Manager)
- (Optional) AgentCore Runtime ARN to enable serverless agent execution

5. Run the application:

```bash
# Run in background
./run.sh start

# or run for local test using uv
uv run uvicorn app:app --host 127.0.0.1 --port 8080 --reload 
```

The server will start on http://localhost:8080 .

## Deployment Options

### Local / EC2
Default mode. Run the full application with Gradio Web UI and all modules.

### AgentCore Runtime (Serverless Agent)

Deploy the AI Agent backend to AWS Bedrock AgentCore Runtime for serverless execution (up to 8 hours, SSE streaming). The Gradio Web UI still runs on EC2/Lambda and calls AgentCore remotely.

```bash
# Deploy agent to AgentCore Runtime
.venv/bin/agentcore deploy

# Enable remote mode in .env
USE_AGENTCORE=true
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
```

See [AgentCore Deployment Guide](./deploy/agentcore/deployment-guide.md) for full details.

## License

MIT License - see LICENSE file for details
