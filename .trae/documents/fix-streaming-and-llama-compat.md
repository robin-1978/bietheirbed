# 修复计划：流式输出 + llama.cpp 兼容性

## 问题分析

### 问题1：没有流式输出
当前 `Agent.run()` 使用 `self._llm.chat()`（非流式），等待完整响应后才 yield 事件。
用户看到的是：等很久 → 突然出现一大段文字，没有任何动态输出感。

`LLMProvider.chat_stream()` 已经实现了 SSE 流式解析，但 Agent 和 ChatUI 都没有使用它。

### 问题2：llama.cpp 仍然报错
从 server 日志看：
- `reasoning-budget: deactivated (natural end)` — 模型推理结束
- `stop: cancel task` — 任务被取消
- `n_tokens = 1300, truncated = 0` — 生成了1300个token

可能的错误原因：
1. **Qwen 3.5 4B 的 thinking/reasoning 模式**：Qwen3.5 默认开启 `<think/>` 推理模式，模型输出包含 `<think...>推理过程</think/>` 标签，这些标签被当作 content 返回，导致 Agent 误判
2. **max_tokens 过大**：默认 2048，对于 4B 小模型可能超出上下文限制
3. **系统提示词太长**：包含所有工具描述的系统提示词可能占用大量 token

## 修复步骤

### Step 1: Agent 改用流式调用
修改 `Agent.run()` 使用 `self._llm.chat_stream()` 代替 `self._llm.chat()`：
- 流式接收 content chunks，逐块 yield `thought` 事件
- 流式接收 tool_calls，在 [DONE] 时 yield `tool_call` 事件
- 新增 `stream_delta` 事件类型，让 UI 能逐字显示

### Step 2: 新增 AgentEvent 类型支持流式
在 `AgentEvent` 中添加：
- `type="stream_delta"` — 流式文本增量，UI 应追加显示而非换行
- `type="stream_start"` — 流式输出开始标记
- `type="stream_end"` — 流式输出结束标记

### Step 3: ChatUI 支持流式显示
修改 `_process_events()` 方法：
- `stream_delta` 事件：使用 `Console.print(end="")` 或 `sys.stdout.write()` 逐字输出
- `stream_start` 事件：打印 AI 标记
- `stream_end` 事件：换行
- 最终的 `final_answer` 事件：用 Rich Markdown 重新渲染完整回答

### Step 4: 处理 Qwen3.5 的 think 标签
Qwen3.5 4B 在 function calling 模式下可能输出 `<think...>推理内容</think/>` 标签。
需要在 Agent 中添加过滤逻辑：
- 从 content 中提取 `<think...>...</think/>` 内容，作为 `thought` 事件
- 去除 think 标签后的内容作为实际回答
- 如果 content 只有 think 标签没有实际内容，说明模型还在推理中

### Step 5: 优化 max_tokens 和系统提示词
- 将默认 `max_tokens` 从 2048 降为 1024（4B 模型够用）
- 系统提示词精简，减少 token 占用
- 在发送给 LLM 的 tools schema 中，精简 description 字段

### Step 6: 修复 RecoveryManager 与流式不兼容问题
当前 `Agent.run()` 通过 `self._recovery.execute_with_recovery(self._llm.chat, ...)` 调用 LLM。
改为流式后不能再用 RecoveryManager 包装（因为 chat_stream 是 async generator）。
改为在 Agent 循环中手动处理重试逻辑。

### Step 7: 更新测试
- 更新 `test_agent.py` 适配新的流式事件类型
- 更新 `test_llm_provider.py` 确保流式测试通过
- 确保覆盖率不低于 80%

## 涉及文件
1. `src/pc_assistant/agent.py` — 核心改动：流式循环 + think 标签处理
2. `src/pc_assistant/ui/chat.py` — 流式显示
3. `src/pc_assistant/llm_provider.py` — 可能需要微调流式解析
4. `src/pc_assistant/config.py` — max_tokens 默认值调整
5. `config/default.yaml` — 配置调整
6. `tests/test_agent.py` — 测试更新
7. `tests/test_ui_chat.py` — 测试更新
