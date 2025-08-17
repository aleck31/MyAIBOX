# MyAIBOX

MyAIBOX( AI百宝箱) is a comprehensive Gen-AI application suite built with FastAPI and Gradio. It features a user-friendly interface that provides access to various AI capabilities, including AI Agent, multimodal chat, text processing，summarization, image and document recognition, code generation, and image creation tools.

## Overview
The application integrates multiple GenAI models, with secure authentication via Amazon Cognito and session management. 
It provides a modular architecture that makes it easy to add new features and AI models.

Its user-friendly Gradio-based web interface provides an intuitive experience.

🎉 **What's New in v2.0**
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
  - Multi-language support

* **Vision Recognition** 👀
  - Image analysis and description
  - Document understanding (PDF support)
  - Multi-model support (Claude/Gemini)
  - Camera and clipboard input support

* **Advanced Features**
  - **Summary** 📰: Document and text summarization
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
├── app.py          # Main application entry point
├── core/           # Core components
│   ├── auth.py        # Authentication handling (cognito)
│   ├── config.py      # Configuration settings
│   ├── logger.py      # Logging configuration
│   ├── module_config.py    # Module configuration
│   ├── service/         # Service integration
│   │   ├── gen_service.py      # General content generation service
│   │   ├── chat_service.py     # Chat service implementation
│   │   ├── draw_service.py     # Image generation service
│   │   └── service_factory.py    # Service creation factory
│   └── session/        # Session management
│       ├── models.py         # Data models for Session
│       └── store.py          # DynamoDB-based session storage
├── genai/               # Genai integration
│   ├── models               # Models implementations
│   │   ├── init.py               # Base LLM interfaces
│   │   ├── providers/            # Model provider integration
│   │   └── model_manager.py      # Model management
│   ├── agents               # Agents implementations
│   │   └── provider.py      #
│   └── tools/              # tools implementations
│       ├── legacy           # Legacy tools for models on Bedrock
│       ├── mcp              # MCP tools for AI Agents
│       └── provider.py      # Unified tool provider
├── common/            # Common modules
│   ├── login/            # Authentication UI
│   ├── setting/          # Module settings
│   └── main_ui.py        # UI settings
├── modules/           # Feature modules
│   ├── init.py           # Base handler class 
│   ├── assistant/        # AI Assistant with tools 
│   ├── persona/          # Chatbot with personality profiles
│   ├── text/             # Text processing
│   ├── summary/          # Text summarization
│   ├── vision/           # Image analysis
│   ├── asking/           # Q&A with thinking
│   ├── coding/           # Code-related features
│   └── draw/             # Image generation
└── utils/             # Utility functions
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

### 🎯 Best Practices

- **Simple functions** → Legacy tools
- **Basic utilities** → Strands tools (automatic)
- **Complex integrations** → MCP tools
- Only enable necessary Legacy tools for better performance
- Use "Test Connection" for MCP server validation

For detailed documentation, see [Tool System Architecture](./docs/tool-system-architecture.md).

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
- AWS region
- Cognito user pool details
- DynamoDB table names
- Model configurations

5. Run the application:

```bash
# Run in background
./run.sh start

# or run for local test using uv
uv run uvicorn app:app --host 127.0.0.1 --port 8080 --reload 
```

The server will start on http://localhost:8080 .

## License

MIT License - see LICENSE file for details
