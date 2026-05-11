# Fix Plan: TUI 增强 + ReAct 循环修复 + 搜索质量 + 推送 GitHub

## 问题分析

### 问题 1：思考内容（think）没有流式输出
当前行为：
- Agent 在流式输出时，`<think...>...</think >` 内容被 `_strip_think_tags` 过滤掉了
- `stream_delta` 事件只发送过滤后的内容，思考过程完全不可见
- `thought` 事件只在流结束后一次性发送完整思考内容（第 216-221 行 agent.py）
- 用户在 LLM 思考时看到的是空白，没有任何反馈

**应该的行为**：
- 思考内容应该**流式实时显示**，让用户知道 LLM 正在工作
- 思考完成后**自动折叠**，只保留一行摘要（如 "💭 Thinking... (click to expand)"）
- 最终回答正常显示

### 问题 2：CLI 无法中断 LLM 生成
当前行为：
- `ChatUI.run()` 中 `await self._process_events(user_input)` 是阻塞的
- 用户按 Ctrl+C 会直接退出整个程序（被 `async_main` 的 `KeyboardInterrupt` 捕获）
- 无法在 LLM 生成过程中中断并重新输入

**应该的行为**：
- 在 LLM 生成/工具执行过程中，按 Ctrl+C 或 Esc 中断当前操作
- 中断后回到输入提示符，可以重新输入
- 不退出程序

### 问题 3：CLI/TUI 功能太弱
当前缺失的功能：
1. **无法中断** — 上面的问题
2. **思考内容不可见** — 上面的问题
3. **没有多行输入** — 无法输入多行消息
4. **没有状态指示** — LLM 思考时没有 spinner/进度提示
5. **工具执行没有实时反馈** — 工具执行时只显示参数，没有进度
6. **没有会话持久化** — 退出后对话丢失
7. **没有主题切换** — 暗色/亮色

### 问题 4：搜索中文结果质量差
DuckDuckGo 对中文搜索完全不可用。需要添加 Bing 搜索后端。

### 问题 5：ReAct 循环在工具调用后可能卡住
- think-only 回答导致空内容循环
- 空回答导致无限循环
- 差的工具结果导致模型无法生成最终回答

### 问题 6：推送到 GitHub
代码需要推送到 `https://github.com/Robin-1978/BieTheirBed`

---

## 修复步骤

### Step 1: Agent 层 — 思考内容流式输出
修改 `src/pc_assistant/agent.py`：

当前 `stream_delta` 只发送过滤后的内容。需要改为：
- 新增 `stream_think_delta` 事件类型，用于流式发送思考内容
- 在流式处理中，跟踪当前是否在 `<think...>` 标签内
- 在 think 标签内时，发送 `stream_think_delta` 事件
- 在 think 标签外时，发送 `stream_delta` 事件
- `thought` 事件保留，在流结束时发送完整思考内容（用于折叠摘要）

具体实现：
```python
# 在 run() 方法的流式循环中
in_think = False
think_buffer = ""

# 处理每个 chunk.delta_content
if chunk.delta_content:
    full_content += chunk.delta_content
    
    # 检测 think 标签状态变化
    if "<think" in chunk.delta_content and not in_think:
        in_think = True
        # 发送 think_start 事件
        yield AgentEvent(type="think_start", iteration=iteration)
    
    if in_think:
        think_buffer += chunk.delta_content
        # 提取纯思考文本（去掉标签）
        think_text = _extract_think_text(chunk.delta_content)
        if think_text:
            yield AgentEvent(type="stream_think_delta", content=think_text, iteration=iteration)
    else:
        # 正常内容流式输出
        clean, _ = _strip_think_tags(full_content)
        # ... 现有逻辑
    
    if "</think" in chunk.delta_content and in_think:
        in_think = False
        yield AgentEvent(type="think_end", iteration=iteration)
```

### Step 2: Agent 层 — 修复 think-only 和空回答
修改 `src/pc_assistant/agent.py`：

1. **think-only 回答**：当 `clean_content` 为空但 `full_content` 不为空（即只有思考内容）时：
   - 添加一条用户消息 "Please provide your answer based on your thinking."
   - 继续循环，让 LLM 基于思考给出回答
   - 添加计数器，最多重试 2 次

2. **空回答**：当 `full_content` 为空且没有 tool_calls 时：
   - 添加一条系统消息 "You did not produce any output. Please respond."
   - 最多重试 2 次，之后返回默认回答

3. **连续空回答计数器**：
   ```python
   empty_response_count = 0
   max_empty_retries = 2
   ```

### Step 3: TUI 层 — 思考内容流式显示 + 自动折叠
修改 `src/pc_assistant/ui/chat.py`：

1. **流式显示思考内容**：
   - `think_start` 事件：显示 "💭 Thinking..." 标题，开始收集思考文本
   - `stream_think_delta` 事件：实时显示思考文本（dim italic 样式）
   - `think_end` 事件：折叠思考内容，只显示一行摘要

2. **自动折叠实现**（使用 Rich 的 Collapsible 或自定义）：
   - Rich 没有 Collapsible 组件，但可以用 `Panel` + 缩进来模拟
   - 思考完成后，清除已显示的思考文本
   - 替换为一行折叠摘要：`💭 Thought for Xs (内容摘要...)`
   - 如果用户想看完整思考，可以点击或按快捷键展开（简化版：直接显示摘要行）

3. **简化方案**（不依赖终端交互能力）：
   - 思考时：实时显示 `💭 <thinking text>`（dim italic）
   - 思考完成：打印换行，然后正常显示回答
   - 不做折叠（终端环境限制），但用视觉区分（dim + 缩进）

### Step 4: TUI 层 — 中断支持
修改 `src/pc_assistant/ui/chat.py` 和 `src/pc_assistant/agent.py`：

1. **Agent 添加取消机制**：
   ```python
   class Agent:
       def __init__(self, ...):
           self._cancelled = False
       
       def cancel(self):
           self._cancelled = True
       
       async def run(self, user_input):
           self._cancelled = False
           # 在循环开始和关键点检查
           if self._cancelled:
               yield AgentEvent(type="cancelled", content="Operation cancelled by user")
               return
   ```

2. **ChatUI 使用 asyncio 信号处理**：
   - 在 `_process_events` 中，使用 `asyncio.shield` + 超时来检测中断
   - 或者更简单：在事件循环中注册 signal handler，设置 `agent._cancelled = True`
   - Windows 上使用 `signal.SIGINT`（Ctrl+C）

3. **具体实现**：
   ```python
   async def _process_events(self, user_input: str) -> None:
       self._agent._cancelled = False
       
       # 创建中断事件
       cancel_event = asyncio.Event()
       
       def on_interrupt():
           cancel_event.set()
           self._agent.cancel()
       
       # Windows: 使用线程监听键盘
       # 简化方案：捕获 KeyboardInterrupt
       try:
           async for event in self._agent.run(user_input):
               if cancel_event.is_set():
                   break
               # ... 处理事件
       except KeyboardInterrupt:
           self._agent.cancel()
           self._print_warning("Operation cancelled.")
   ```

4. **更实用的方案**：在单独线程中运行 agent 事件处理，主线程监听输入：
   - 使用 `asyncio.create_task` 运行 agent
   - 主循环中用 `input()` 或非阻塞 IO 检测中断命令
   - 检测到中断时取消 task

### Step 5: TUI 层 — 状态指示器（Spinner）
修改 `src/pc_assistant/ui/chat.py`：

- 在 LLM 思考/生成时显示 spinner（⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏）
- 使用 Rich 的 `Status` 或 `Spinner` 组件
- 在 `stream_start` 时启动 spinner
- 在第一个 `stream_delta` 或 `stream_think_delta` 时停止 spinner
- 在工具执行时显示 "🔧 Executing tool..."

### Step 6: 搜索质量 — 添加 Bing 搜索后端
修改 `src/pc_assistant/tools/web.py`：

1. 添加 `_search_bing()` 方法：
   - URL: `https://www.bing.com/search?q={query}&setlang=zh-Hans`（中文）
   - URL: `https://www.bing.com/search?q={query}`（英文）
   - 使用 httpx + BeautifulSoup 解析 HTML
   - 提取 `.b_algo` 元素中的标题、URL、摘要

2. 搜索策略：
   - 中文查询：Bing 优先，DDG 备选
   - 英文查询：DDG 优先，Bing 备选
   - 任一成功即返回，不串行等待两个

3. 结果去重和过滤：
   - 按 URL 去重
   - 过滤空 snippet
   - 默认 5 条结果（减少 token 消耗）

### Step 7: 系统提示词 — 添加差工具结果应对指导
修改 `src/pc_assistant/context/system_prompt.py`：

在 Tool Usage Rules 中添加：
```
7. If a tool returns irrelevant or unhelpful results, acknowledge this and provide the best answer you can based on your knowledge, or suggest an alternative approach. Do NOT keep calling tools hoping for better results.
```

### Step 8: 推送到 GitHub
```bash
git add -A
git commit -m "feat: streaming think, TUI interrupt, Bing search, ReAct robustness"
git remote add origin https://github.com/Robin-1978/BieTheirBed.git
git push -u origin main --force
```

---

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `src/pc_assistant/agent.py` | 思考流式输出、think-only 处理、空回答检测、取消机制 |
| `src/pc_assistant/ui/chat.py` | 思考流式显示、自动折叠、中断支持、Spinner、事件处理 |
| `src/pc_assistant/tools/web.py` | Bing 搜索后端、搜索策略优化、结果去重 |
| `src/pc_assistant/context/system_prompt.py` | 差工具结果应对指导 |
| `tests/test_agent.py` | 新增 think-only、空回答、取消测试 |
| `tests/test_tools_web.py` | 新增 Bing 搜索测试 |
| `tests/test_ui_chat.py` | 新增中断、思考显示测试 |

## 优先级

1. **P0（核心功能）**：Step 1 (思考流式) + Step 2 (ReAct 修复) + Step 4 (中断支持)
2. **P1（重要）**：Step 6 (Bing 搜索) + Step 7 (提示词)
3. **P2（增强）**：Step 3 (折叠) + Step 5 (Spinner)
4. **P3（收尾）**：Step 8 (GitHub 推送)
