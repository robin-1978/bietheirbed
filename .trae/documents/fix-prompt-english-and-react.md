# 修复计划：系统提示词改英文通用 + ReAct 循环修复 + 搜索优化

## 问题分析

### 问题1：系统提示词不应该是中文，不应包含特定时间
用户明确要求：
- 系统提示词使用**英语**（通用 agent，不绑定语言）
- **不要**在系统提示词中硬编码特定日期时间（"今天是2026年5月11日"）
- 日期时间等信息应通过**单独的上下文注入**提供，而非写在通用提示词中

### 问题2：ReAct 循环在工具调用后卡住
用户问"查一下上海天气"，Agent 调用 web search → 得到结果 → 但之后没有产生 final_answer。

**根本原因分析**：
看 Agent.run() 的流式循环逻辑（第 164-191 行）：
1. 流式接收 chunks，累积 `full_content` 和 `tool_calls_from_stream`
2. 在流式过程中，`chunk.delta_tool_calls` 只在中间 chunks 中有值
3. 但在 `[DONE]` 时，`chat_stream()` 才 yield 最终完整的 tool_calls
4. **关键 bug**：第 187 行 `if chunk.delta_tool_calls:` — 中间 chunks 的 `delta_tool_calls` 是空列表 `[]`（因为只在 [DONE] 时才 yield 完整 tool_calls），所以 `tool_calls_from_stream` 可能被覆盖为空列表

让我再仔细看：在 `chat_stream()` 中，中间 chunks yield `delta_tool_calls=[]`（第 216 行），只有 [DONE] 时才 yield 完整的 tool_calls（第 164 行）。所以第 187-188 行：
```python
if chunk.delta_tool_calls:
    tool_calls_from_stream = chunk.delta_tool_calls
```
空列表 `[]` 是 falsy，所以不会覆盖。但 [DONE] chunk 的 `delta_tool_calls` 包含完整 tool_calls，会正确设置。

**那为什么卡住？** 可能是：
1. 模型在收到搜索结果后，又产生了 `<think...>` 推理内容，推理时间很长
2. 模型产生了另一个工具调用，但参数解析失败
3. `max_tokens=1024` 不够，模型输出被截断

**更可能的原因**：4B 模型在 function calling 模式下，收到工具结果后，可能不会正确生成最终回答，而是继续生成 `<think...>` 内容直到 max_tokens 耗尽，然后 finish_reason="length"（而非 "stop"），导致 Agent 认为这不是最终回答，继续循环。

### 问题3：DuckDuckGo 搜索中文结果质量差
搜索"上海天气"返回了完全不相关的结果（百度企业信息、色情网站、YouTube）。

**原因**：DuckDuckGo 对中文搜索支持很差。需要改进搜索策略。

## 修复步骤

### Step 1: 系统提示词改为英文通用版
重写 `build_system_prompt()`：
- 全部使用英文
- 不包含任何特定时间/日期
- 通用 agent 角色定义
- 清晰的工具使用规则（英文）
- 日期时间通过 `extra_instructions` 参数单独注入

### Step 2: Agent 在系统提示词外单独注入当前时间
在 `Agent.__init__()` 和 `reset_conversation()` 中：
- 系统提示词使用通用英文版
- 额外添加一条系统消息注入当前时间："Current date: 2026-05-11 (Monday)"
- 这样系统提示词本身是通用的，时间信息是动态注入的

### Step 3: 修复 ReAct 循环 - 处理 finish_reason="length"
在 `Agent.run()` 中：
- 当 `finish_reason="length"` 时，说明模型输出被截断
- 如果此时有 tool_calls，正常处理
- 如果没有 tool_calls 且有 content，视为最终回答（即使被截断）
- 避免无限循环

### Step 4: 修复 ReAct 循环 - 处理空回答
当模型返回空内容且没有 tool_calls 时：
- 视为最终回答，返回"我无法回答这个问题"
- 避免继续循环

### Step 5: 改进搜索 - 添加中文搜索支持
修改 `WebTool._search()`：
- 对中文查询，使用 `region="cn-zh"` 参数
- 增加搜索结果数量（默认 8 → 5，减少 token 消耗）
- 改进 snippet 展示格式

### Step 6: 推送到 GitHub
```bash
git remote add origin https://github.com/Robin-1978/BieTheirBed.git
git push -u origin main --force
```

## 涉及文件
1. `src/pc_assistant/context/system_prompt.py` — 英文通用版
2. `src/pc_assistant/agent.py` — 时间注入 + ReAct 循环修复
3. `src/pc_assistant/tools/web.py` — 中文搜索改进
4. `tests/test_context.py` — 测试更新
5. `tests/test_agent.py` — 新增 finish_reason=length 测试
