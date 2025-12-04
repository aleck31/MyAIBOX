# AWS Bedrock Converse API 推理模型用法

参考 AWS 官方文档，推理模型在 Bedrock Converse API 中的调用方法。

## 推理模型分类

实际上有 **3种处理模式**：

### 1. Claude Extended Thinking 模型

**支持的模型：**
- Claude 3.7 Sonnet (`anthropic.claude-3-7-sonnet-20250219-v1:0`)
- Claude Opus 4 (`anthropic.claude-opus-4-20250514-v1:0`)
- Claude Sonnet 4 (`anthropic.claude-sonnet-4-20250514-v1:0`)
- Claude Sonnet 4.5 (`anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Claude Haiku 4.5 (`anthropic.claude-haiku-4-5-20251001-v1:0`)

**参数格式：**

```json
{
  "additionalModelRequestFields": {
    "thinking": {
      "type": "enabled",
      "budget_tokens": 4000
    }
  }
}
```

**共同特点：**
- 最小 thinking budget: 1,024 tokens
- 不兼容 `temperature`, `top_p`, `top_k` 修改
- 需要流式处理当 `max_tokens` > 21,333

**重要差异：**
- **Claude 3.7**: 返回完整的 thinking 输出
- **Claude 4/4.5**: 返回摘要版 thinking（仍按完整 tokens 计费）
- **Claude 4.5**: 只能指定 `temperature` 或 `top_p` 之一，不能同时使用

### 2. DeepSeek R1 (`us.deepseek.r1-v1:0`)

**自动推理模型**，无需额外参数：

```json
{
  "prompt": "string",
  "temperature": 0.7,
  "top_p": 0.9,
  "max_tokens": 4096
}
```

**特点：**
- 自动输出推理过程，无需 thinking 参数
- 使用跨区域推理配置文件 ID
- 不支持工具调用
- 最大 tokens: 32,768

### 3. 混合推理模型（DeepSeek V3.1 + Qwen3）

**DeepSeek V3.1** (`deepseek.v3-v1:0`) 和 **Qwen3** (`qwen.qwen3-235b-a22b-2507-v1:0`) 使用相同参数：

```json
{
  "additionalModelRequestFields": {
    "thinking": true,
    "thinkBudget": 4000
  }
}
```

**共同特点：**
- 不支持 `stopSequences` 参数
- 不支持工具调用
- 需要显式启用 thinking 模式
- 参数格式完全一致

## 统一处理逻辑

```python
def get_reasoning_params(model_id, budget_tokens=4000):
    # Claude 3.7, 4, 4.5 系列
    if any(x in model_id for x in ['claude-3-7', 'claude-4', 'claude-sonnet-4', 'claude-haiku-4', 'claude-opus-4']):
        return {"thinking": {"type": "enabled", "budget_tokens": budget_tokens}}
    # DeepSeek R1 自动推理
    elif 'deepseek.r1' in model_id or 'us.deepseek.r1' in model_id:
        return {}
    # DeepSeek V3.1 和 Qwen3
    elif model.capabilities.reasoning:
        return {"thinking": True, "thinkBudget": budget_tokens}
    else:
        return {}

def should_skip_stop_sequences(model_id):
    # DeepSeek V3.1 和 Qwen3 不支持 stopSequences
    return 'deepseek.v3' in model_id or 'qwen' in model_id

def prepare_inference_params(model_id, temperature, top_p):
    # Claude 4.5 只能用 temperature 或 top_p 之一
    is_claude_45 = 'claude-haiku-4-5' in model_id or 'claude-sonnet-4-5' in model_id
    
    if is_claude_45:
        # 优先使用 temperature
        return {"temperature": temperature} if temperature else {"topP": top_p}
    else:
        # 其他模型可以同时使用
        return {"temperature": temperature, "topP": top_p}
```

## 参考文档

- [AWS Bedrock Extended Thinking](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-extended-thinking.html)
- [Claude Thinking Differences](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-thinking-differences.html)
- [Claude 4.5 Parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-request-response.html)
- [DeepSeek Models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-deepseek.html)
- [Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
