# 完成上次计划 + System Prompt 注入架构优化

## 上次计划遗留

Task 1-10 已全部实现（276 测试通过），仅剩 Task 11（端到端验证）未完成。
同时发现并修复了一个关键 bug：llama.cpp 要求 system message 只能在开头，但 Agent 在对话中间插入了 system 消息。

## 新问题：System Prompt 存储架构

### 当前架构（有问题）
```
ConversationManager._messages = [
    Message(role="system", content=system_prompt),   ← 存在历史里
    Message(role="system", content=date_context),     ← 存在历史里
    Message(role="user", content="hello"),
    Message(role="assistant", content="hi"),
    Message(role="user", content="查天气"),            ← 第2轮
    ...
]
```

**问题：**
1. System prompt 占用 context window budget，随对话增长可能被 truncator 截断
2. 每次 `reset_conversation()` 需要重新添加 system prompt
3. Date context 是静态的（初始化时注入），长时间运行后时间信息过时
4. llama.cpp 要求 system message 只能在开头，但 truncator 的 summary 消息可能插入 system 消息到中间

### 优化方案：System Prompt 每次请求时注入头部

```
ConversationManager._messages = [
    Message(role="user", content="hello"),
    Message(role="assistant", content="hi"),
    Message(role="user", content="查天气"),
    ...
]

# 每次调用 LLM 时，在 get_messages_for_llm() 中动态注入：
messages = [
    {"role": "system", "content": system_prompt},     ← 动态注入
    {"role": "system", "content": date_context()},     ← 动态注入（实时时间）
    ...conversation_history...
]
```

**优点：**
1. System prompt 永远不会被截断（在 budget 计算之外）
2. Date context 每次请求都是最新的
3. Conversation history 只包含真正的对话，更干净
4. truncator 不需要特殊处理 system 消息
5. 符合 llama.cpp 的 system message 必须在开头的要求

---

## 修复步骤

### Step 1: 重构 ConversationManager — 分离 system prompt
修改 `src/pc_assistant/context/conversation.py`：
- 新增 `set_system_context(system_prompt, date_context)` 方法，存储但不放入 `_messages`
- `get_messages()` 仍然返回纯对话历史（不含 system）
- `get_messages_for_llm()` 在返回时动态在头部注入 system prompt + date context
- `clear()` 只清除对话历史，不清除 system context
- `summarize_old_messages()` 不再生成 system 角色的 summary（之前已改为 user，确认一致性）

### Step 2: 重构 Agent — 使用新的注入方式
修改 `src/pc_assistant/agent.py`：
- `__init__()` 中不再调用 `self._conversation.add("system", ...)`，改为 `self._conversation.set_system_context(system_prompt, date_context)`
- `run()` 中每次迭代调用 `self._conversation.get_messages_for_llm()` 获取带 system 注入的消息
- `reset_conversation()` 只清除对话历史，system context 保持不变
- Date context 每次请求时自动更新（在 `get_messages_for_llm()` 中调用 `_build_date_context()`）

### Step 3: 重构 Truncator — 不再处理 system 消息
修改 `src/pc_assistant/context/truncator.py`：
- `truncate_messages()` 不再需要 `preserve_system` 参数
- 不再从 messages 中提取 system 消息
- 直接对所有消息做 budget 计算
- summary 消息使用 user 角色

### Step 4: 更新测试
- `test_context.py` — 更新 ConversationManager 测试
- `test_agent.py` — 更新 reset_conversation 测试（不再检查 system 消息数量）
- `test_truncator.py` — 更新 truncator 测试（移除 preserve_system 相关测试）

### Step 5: 运行完整测试套件 + 推送 GitHub
- 276+ 测试全部通过
- `git add -A && git commit && git push`
