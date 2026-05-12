# Fix: 工具框错位 + 中文记忆不生效 + 重复输出

## 问题 1：工具调用框与 Spinner 错位

### 根因
```python
elif event.type == "tool_call":
    self._spinner.start(f"Executing {event.tool_name}...")  # 启动 spinner（后台线程写 stdout）
    spinner_active = True
    self._print_tool_call(event.tool_name, event.tool_args)  # Rich Panel 写 console
```

Spinner 在后台线程写 `sys.stdout`（`\r  ⠋ Executing web...`），同时 Rich Panel 写 console，两者交错导致：
```
  ⠋ Executing web...╭────────── 🔧 web ──────────╮
```

### 修复
**先停止 spinner，再打印工具框，再启动新 spinner**：
```python
elif event.type == "tool_call":
    self._spinner.stop()  # 先停止
    spinner_active = False
    if event.blocked:
        self._print_warning(...)
    else:
        self._print_tool_call(...)  # 打印工具框
        self._spinner.start(f"Executing {event.tool_name}...")  # 再启动
        spinner_active = True
```

## 问题 2：中文记忆不生效

### 根因
`_PREFERENCE_PATTERNS` 全部是英文正则：
```python
(r"(?:i (?:live|am based|reside)\s+(?:in|at)\s+)(.+?)(?:\.|!|$)", "location", "conversation"),
```

用户说 "我住在上海"，不匹配任何英文模式，所以记忆没有提取。

### 修复方案
**不使用正则模式匹配，改为让 LLM 自己提取用户偏好**。

具体方案：
1. 移除 `_PREFERENCE_PATTERNS` 和 `extract_from_text()` 的正则匹配
2. 在 system prompt 中添加指令，让 LLM 在识别到用户偏好时调用 `memory` 工具存储
3. 新增 `memory` 工具到工具系统，支持 `store`/`retrieve`/`search`/`delete` 操作
4. LLM 自主决定何时存储记忆（如用户说"我住上海"时，LLM 调用 `memory.store(key="location", value="上海")`）

这样做的好处：
- **通用**：不依赖特定语言的正则，支持中英文
- **智能**：LLM 理解语义，比正则更准确
- **灵活**：LLM 可以提取任意类型的偏好

### memory 工具 schema
```python
{
    "name": "memory",
    "description": "Store, retrieve, search, or delete user preferences and information for long-term memory",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["store", "retrieve", "search", "delete"]},
            "key": {"type": "string", "description": "Memory key (e.g. 'location', 'name', 'preference_editor')"},
            "value": {"type": "string", "description": "Value to store (required for store action)"},
            "category": {"type": "string", "description": "Category: identity, location, preference, workflow, instruction"},
        },
        "required": ["action", "key"],
    },
}
```

### system prompt 添加记忆指令
```
## Memory Rules (IMPORTANT)
- When the user mentions personal information (name, location, preferences, work, etc.), use the `memory` tool with action `store` to save it.
- When answering questions, use `memory` with action `retrieve` or `search` to check if you have relevant user information.
- Examples of what to store: "I live in Shanghai" → store(key="location", value="Shanghai", category="location"), "I prefer dark mode" → store(key="preference_theme", value="dark mode", category="preference")
```

## 问题 3：重复输出仍然存在

### 根因
我之前的修复 `if not first_content_received and event.content:` 应该有效，但需要验证代码是否正确保存。

让我重新检查：`stream_delta` 设置 `first_content_received = True`，然后 `final_answer` 检查 `not first_content_received`。逻辑正确。

但可能的问题是：**Agent 的 `run()` 方法在多轮迭代中，每轮都会触发 `stream_start`**，而 `stream_start` 会重置 `first_content_received = False`。如果 LLM 在工具调用后再次流式输出回答，`stream_start` 重置了标志，然后 `stream_delta` 设置为 True，然后 `final_answer` 检查 `not True` = False，不会重复。逻辑应该正确。

**等等**，让我再仔细看输出。第一次输出用 `- **白天**`（原始 markdown），第二次用 `• 白天`（渲染后 markdown）。这说明 `final_answer` 确实在渲染。可能的原因：`stream_delta` 通过 `self._console.print(event.content, end="")` 输出，但 `self._console.print` 在 Rich 中可能会缓冲输出，导致 `first_content_received` 虽然是 True，但 `final_answer` 的 Markdown 渲染仍然执行。

**实际上**，让我重新检查代码。我怀疑问题出在 `self._console.print(event.content, end="", highlight=False)` — 这个 print 调用可能不会立即输出，而是被 Rich 缓冲。然后 `final_answer` 的 `self._console.print(Markdown(event.content))` 又输出了一次。

但我的检查 `if not first_content_received` 应该阻止第二次输出。除非... 代码没有正确保存？

让我直接读取文件确认。

## 修改步骤

### Step 1: 修复工具框错位
修改 `src/pc_assistant/ui/chat.py`：
- `tool_call` 事件：先 stop spinner，再打印工具框，再 start spinner

### Step 2: 新增 memory 工具
创建 `src/pc_assistant/tools/memory_tool.py`：
- 实现 `MemoryTool` 类，支持 store/retrieve/search/delete 操作
- 调用 `Agent._memory` 的方法

### Step 3: 注册 memory 工具
修改 `src/pc_assistant/agent.py`：
- 在 `_register_builtin_tools()` 中注册 `MemoryTool`
- `MemoryTool` 需要访问 `Agent._memory`，所以传入 memory 引用

### Step 4: 更新 system prompt
修改 `src/pc_assistant/context/system_prompt.py`：
- 添加 Memory Rules 指令

### Step 5: 移除正则提取
修改 `src/pc_assistant/agent.py`：
- 移除 `run()` 中的 `extract_from_text()` 调用
- 记忆提取改为由 LLM 通过工具调用完成

### Step 6: 确认重复输出修复
- 读取 chat.py 确认 `final_answer` 的 `not first_content_received` 检查存在
- 如果不存在，重新添加

### Step 7: 更新测试 + 运行
- 更新 `test_memory.py`（移除正则提取测试）
- 新增 `test_tools_memory.py`
- 运行完整测试套件

### Step 8: 提交推送
