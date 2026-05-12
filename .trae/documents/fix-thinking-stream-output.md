# 修复 Thinking 内容流式输出 — 计划文档

## 问题分析

用户提问："是不是我们没有流式输出思考的内容？"

经代码审查，发现 **根本问题**：

1. `llm_provider.py` 的 `chat_stream()` 只提取了 `delta.get("content")`，完全忽略了 `reasoning_content` / `thinking` 字段
2. Qwen3.5 等模型通过 llama.cpp 的 OpenAI-compatible API 返回 thinking 内容时，通常使用独立的 `reasoning_content` 字段（类似 DeepSeek API 格式），而不是包裹在 `<think>` 标签内
3. 当前 `_ThinkStreamParser` 只解析 `<think>` 标签，对 `reasoning_content` 字段完全无感知
4. 结果就是：thinking 内容在流式输出中完全丢失，用户看不到任何思考过程

## 修复步骤

### Step 1: StreamChunk 新增 thinking 字段

修改 `src/pc_assistant/llm_provider.py`：
- `StreamChunk` 新增 `delta_thinking: str = ""` 字段
- `chat_stream()` 中，在提取 `delta_content` 之后，同时提取 `delta.get("reasoning_content")` 或 `delta.get("thinking")`
- 将 thinking 内容通过 `delta_thinking` 字段 yield 出去

### Step 2: Agent 中将 thinking 内容转为 think 事件

修改 `src/pc_assistant/agent.py`：
- 在 `run()` 的流式循环中，检查 `chunk.delta_thinking`
- 如果有 thinking 内容，通过 `_ThinkStreamParser` 或直接 yield `stream_think_delta` 事件
- 确保 thinking 内容和普通 content 不会重复输出

### Step 3: 优化 Chat UI 的 thinking 展示

修改 `src/pc_assistant/ui/chat.py`：
- 当前 `stream_think_delta` 使用 `Live` panel 只显示最后 300 字符，体验不佳
- 改为直接通过 `sys.stdout.write()` 实时输出 thinking 内容（类似普通 stream_delta 的处理方式）
- `think_start` 时打印 `"\n  💭 Thinking...\n"` 引导
- `think_end` 时打印换行并显示耗时摘要
- 去掉 `transient=True` 的 Live panel，让 thinking 内容保留在终端中

### Step 4: 运行测试并验证

- 运行 `python -m pytest` 确保全部测试通过
- 检查 type/lint 错误

## 预期效果

- Qwen3.5 等模型的 thinking/reasoning 内容能够实时流式展示
- 用户可以在终端中完整看到 AI 的思考过程（不再被截断或隐藏）
- thinking 内容展示方式与普通回答一致，体验统一
