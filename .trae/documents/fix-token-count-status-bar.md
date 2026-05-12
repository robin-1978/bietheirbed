# 修复状态栏 Token 数量统计 — 计划文档

## 问题分析

状态栏和 `/status` 命令中 token 数量始终显示 0。

根因链路：

1. `Agent.run()` 仅使用流式接口 `chat_stream()`
2. `StreamChunk` 没有 `usage` 字段，流式传输中完全丢弃了 token 统计数据
3. `Agent._total_prompt_tokens` 和 `_total_completion_tokens` 声明了但**从未被赋值**，始终为 0
4. UI 层正确读取并展示这些值，但底层永远是 0

### OpenAI 流式 API 的 usage 机制

llama.cpp / OpenAI 兼容 API 在流式模式下，`usage` 字段出现在 **最后一个 chunk**（`[DONE]` 之前），格式如下：
```json
data: {"choices":[],"usage":{"prompt_tokens":3178,"completion_tokens":141,"total_tokens":3319}}
data: [DONE]
```

需要在 `chat_stream()` 中解析这个字段。

## 修复步骤

### Step 1: StreamChunk 新增 usage 字段

修改 `src/pc_assistant/llm_provider.py`：
- `StreamChunk` 新增 `usage: dict[str, Any] = {}` 字段
- Anthropic 回退到非流式时，将 `result.usage` 透传到 `StreamChunk`

### Step 2: chat_stream() 解析流式 usage

修改 `src/pc_assistant/llm_provider.py`：
- 在 `chat_stream()` 的 SSE 解析循环中，从 `chunk_data` 顶层提取 `usage` 字段
- 将 usage 附加到最后一个 `StreamChunk`（`finish_reason` 非空时）或 `[DONE]` 之前的 chunk
- OpenAI 兼容的流式 API 会在 `stream_options: {"include_usage": true}` 时返回 usage，但 llama.cpp 默认在最后一个 chunk 包含 usage，无需额外参数

### Step 3: Agent.run() 中累加 token 计数

修改 `src/pc_assistant/agent.py`：
- 在 `run()` 的流式循环中，检查 `chunk.usage`
- 如果有 usage 数据，累加到 `_total_prompt_tokens` 和 `_total_completion_tokens`
- 注意：OpenAI 格式用 `prompt_tokens` / `completion_tokens`，Anthropic 用 `input_tokens` / `output_tokens`

### Step 4: 运行测试并验证

- 运行 `python -m pytest` 确保全部测试通过
- 更新 test_agent.py 中 `total_tokens == 0` 的断言（如有必要）

## 预期效果

- 状态栏和 `/status` 命令正确显示 prompt/completion/total token 数量
- 每次 LLM 调用后 token 计数累加，而非始终为 0
