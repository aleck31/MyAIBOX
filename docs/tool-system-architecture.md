# MyAIBOX 工具系统架构文档

## 概述

MyAIBOX 采用了一个统一的工具系统架构，支持三种不同类型的工具：Legacy工具、Strands内置工具和MCP（Model Context Protocol）工具。该架构经过优化，提供了高性能、模块化和易于配置的工具集成方案。

## 工具类型

### 1. Legacy工具
- **定义**: 基于Python函数的传统工具，使用`@tool`装饰器转换为Strands兼容格式
- **特点**: 
  - 模块级别配置
  - 用户可选择启用/禁用
  - 适合简单的功能实现
- **示例**: `get_weather`, `search_wikipedia`, `generate_image`

### 2. Strands内置工具
- **定义**: Strands SDK提供的原生工具
- **特点**:
  - 全局启用，无需配置
  - 高性能，原生集成
  - 提供基础功能
- **示例**: `current_time`, `calculator`, `http_request`, `sleep`, `speak`

### 3. MCP工具
- **定义**: 基于Model Context Protocol的外部工具服务器
- **特点**:
  - 全局配置管理
  - 支持多种连接类型（HTTP、stdio、SSE）
  - 可扩展的工具生态系统
- **示例**: `exa-server`, `core-mcp-server`

## 架构组件

### 核心组件

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Module        │    │   Agent Service  │    │  Tool Provider  │
│   Handlers      │───▶│                  │───▶│                 │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Agent Provider  │    │  MCP Server     │
                       │                  │    │  Manager        │
                       └──────────────────┘    └─────────────────┘
```

### 1. ToolProvider (`genai/tools/provider.py`)

**职责**: 统一的工具加载和管理中心

**核心方法**:
```python
def get_tools_and_contexts(self, tool_config: Dict) -> Tuple[List, List]:
    """根据配置加载工具和MCP上下文管理器"""
    
def list_tools(self) -> List[Dict]:
    """列出所有可用工具的信息"""
```

**工具配置格式**:
```python
tool_config = {
    'enabled': True,  # 总开关，便于调试
    'legacy_tools': ['get_weather', 'generate_image'],  # 指定Legacy工具
    'mcp_tools_enabled': True,      # 是否启用MCP工具
    'strands_tools_enabled': True,  # 是否启用Strands工具
}
```

### 2. AgentService (`core/service/agent_service.py`)

**职责**: 提供工具基础设施和默认配置

**核心方法**:
```python
def _get_default_tool_config(self) -> Dict[str, Any]:
    """提供默认工具配置（不读取数据库）"""
    return {
        'enabled': True,
        'legacy_tools': [],  # 空列表，由模块指定
        'mcp_tools_enabled': False,  # 默认禁用MCP
        'strands_tools_enabled': True,
    }
```

### 3. MCPServerManager (`genai/tools/mcp/mcp_server_manager.py`)

**职责**: MCP服务器配置的CRUD操作

**核心功能**:
- 服务器配置的增删改查
- 支持多种服务器类型（HTTP、stdio、SSE）
- 配置持久化到DynamoDB

**服务器配置格式**:
```python
# HTTP类型
server_config = {
    'type': 'http',
    'url': 'https://api.example.com/mcp',
    'disabled': False,
    'args': []
}

# stdio类型
server_config = {
    'type': 'stdio',
    'command': 'uvx',
    'args': ['package@latest'],
    'env': {'LOG_LEVEL': 'ERROR'},
    'disabled': False
}

# SSE类型
server_config = {
    'type': 'sse',
    'url': 'http://localhost:8000/sse',
    'disabled': False
}
```

## 配置管理

### 模块级别配置

**位置**: 模块的handlers.py文件
**用途**: 指定该模块使用的Legacy工具

**示例** (Assistant模块):
```python
# modules/assistant/handlers.py
from core.module_config import module_config

# 从数据库读取模块配置
module_cfg = module_config.get_module_config('assistant')
enabled_legacy_tools = module_cfg.get('enabled_tools', [])

# 构建工具配置
tool_config = {
    'enabled': True,
    'legacy_tools': enabled_legacy_tools,  # 用户在UI中选择的工具
    'mcp_tools_enabled': True,     # Assistant启用MCP
    'strands_tools_enabled': True, # Assistant启用Strands
}
```

### 全局配置

**MCP工具**: 通过Tool Management界面进行全局配置
**Strands工具**: 固定启用，无需配置

## 用户界面

### 1. 模块配置界面 (`common/setting/tab_module.py`)

**功能**: 配置每个模块的Legacy工具
**特点**:
- 只显示Legacy工具选项
- 配置保存到DynamoDB
- 模块级别的精确控制

### 2. 工具管理界面 (`common/setting/tab_tools.py`)

**功能**: 管理MCP服务器
**特点**:
- 添加/删除/启用/禁用MCP服务器
- 测试服务器连接
- 查看服务器提供的工具
- 全局配置管理

## 性能优化

### 1. 按需加载
- MCP客户端只在需要时创建
- 避免启动时的连接开销
- 智能的工具过滤

### 2. 上下文管理
- 使用Strands原生的MCP支持
- 高效的资源管理
- 自动清理连接

### 3. 缓存机制
- 工具注册表缓存
- 配置信息缓存
- 减少数据库查询

## 工具开发指南

### 开发Legacy工具

1. **创建工具函数**:
```python
# genai/tools/legacy/my_tools.py
def my_custom_tool(param1: str, param2: int) -> str:
    """工具描述
    
    Args:
        param1: 参数1描述
        param2: 参数2描述
        
    Returns:
        结果描述
    """
    # 工具实现
    return f"Result: {param1} - {param2}"
```

2. **注册工具**:
```python
# genai/tools/legacy/tool_registry.py
from .my_tools import my_custom_tool

legacy_tool_registry.register_tool("my_custom_tool", my_custom_tool)
```

3. **在模块中使用**:
用户可以在模块配置界面选择启用该工具

### 集成MCP服务器

1. **通过UI添加**:
   - 访问Tool Management界面
   - 点击"Add New MCP Server"
   - 填写服务器信息

2. **配置示例**:
```python
# HTTP服务器
{
    "name": "my-mcp-server",
    "type": "http",
    "url": "https://api.example.com/mcp"
}

# stdio服务器
{
    "name": "local-mcp-server", 
    "type": "stdio",
    "command": "python",
    "args": ["-m", "my_mcp_package"]
}
```

## 故障排除

### 常见问题

1. **工具加载失败**
   - 检查工具配置格式
   - 验证工具注册是否正确
   - 查看日志中的错误信息

2. **MCP连接问题**
   - 使用"Test Connection"功能
   - 检查服务器URL和参数
   - 验证网络连接

3. **性能问题**
   - 使用`'enabled': False`禁用工具进行调试
   - 检查MCP服务器响应时间
   - 优化工具过滤配置

### 调试技巧

1. **启用详细日志**:
```python
import logging
logging.getLogger('aibox').setLevel(logging.DEBUG)
```

2. **禁用特定工具类型**:
```python
tool_config = {
    'enabled': True,
    'legacy_tools': [],
    'mcp_tools_enabled': False,  # 禁用MCP进行调试
    'strands_tools_enabled': True,
}
```

3. **使用工具列表API**:
```python
from genai.tools.provider import tool_provider
tools_info = tool_provider.list_tools()
print(tools_info)
```

## 最佳实践

### 1. 工具选择原则
- **Legacy工具**: 简单、模块特定的功能
- **Strands工具**: 基础、通用的功能
- **MCP工具**: 复杂、外部服务集成

### 2. 性能考虑
- 只启用必需的工具
- 合理配置MCP服务器
- 定期清理无用的工具配置

### 3. 安全考虑
- 验证MCP服务器的可信度
- 限制工具的权限范围
- 定期更新工具和服务器

## 版本历史

### v2.0 (当前版本)
- 统一的工具配置格式
- 优化的性能和架构
- 简化的配置管理
- 完整的MCP支持

### v1.x (历史版本)
- 基础的Legacy工具支持
- 简单的工具注册机制
- 有限的配置选项

## 相关文档

- [Strands Agents SDK参考](./strands-agents-sdk-reference.md)
- [工具管理评估](./tool-management-evaluation.md)
- [API文档](../README.md)

---

*最后更新: 2025-08-17*
*版本: 2.0*
