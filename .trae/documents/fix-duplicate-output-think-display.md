# Fix: 重复输出 + Thinking 内容优雅展示

## 问题 1：最终回答输出两次（输出2次）

### 根因
在 `_process_events()` 中，内容被输出了两次：

1. **流式输出阶段**（`stream_delta` 事件）→ `sys.stdout.write(event.content)` — 实时显示每个字符
2. **最终答案阶段**（`final_answer` 事件）→ `self._console.print(Markdown(event.content))` — 再次渲染完整 Markdown

所以用户看到：
```
AI> 好的，知道了！上海是...（流式输出）
好的，知道了！上海是...（Markdown 渲染，第二次）   ← 重复！
```

### 修复方案
- **移除 `final_answer` 的 Markdown 渲染**
- 流式输出已经显示了完整内容，不需要再打印一次
- 如果流式输出没有产生任何内容（非正常路径），才 fallback 打印

## 问题 2：Thinking 内容不可见/不优雅

### 根因分析
当前 thinking 显示流程：
```
💭 Thinking...                    ← think_start
<think 内容直接写到 stdout>        ← stream_think_delta（sys.stdout.write，无样式）
💭 Thought for 0.5s: summary...  ← think_end
AI> 回答内容                      ← stream_delta + final_answer
```

问题：
1. `stream_think_delta` 用 `sys.stdout.write()` 原始写入，没有 Rich 样式
2. 思考内容和后续的 AI> 输出混在一起，视觉上不清晰
3. 模型可能不总是输出 `<think...>` 标签（简单问题可能跳过）

### 修复方案：优雅的折叠式思考展示

使用 Rich 的 Panel 实现折叠效果：

**思考中状态：**
```
╭──────────────────────────────────────╮
│ 💭 Thinking... ⠋                  │ ← 带 spinner 动画
╰──────────────────────────────────────╯
```

**思考完成后（自动折叠）：**
```
╭──────────────────────────────────────╮
│ 💭 Thought 0.8s                     │ ← 一行摘要
│    用户说住在上海，应该记住这个信息   │ ← 可展开查看
╰──────────────────────────────────────╯
```

**实现细节：**
1. `think_start` — 开始收集思考文本，用 Rich Panel 显示带 spinner 的思考框
2. `stream_think_delta` — 收集到 buffer 中（不直接写 stdout），用 Live 更新 Panel 内容
3. `think_end` — 替换为折叠摘要 Panel
4. 不再使用 `sys.stdout.write` 写思考内容，全部走 Rich Console

---

## 修改步骤

### Step 1: 修复 final_answer 重复输出
修改 `src/pc_assistant/ui/chat.py`：
```python
elif event.type == "final_answer":
    if spinner_active:
        self._spinner.stop()
        spinner_active = False
    if event.content and not first_content_received:
        if self._console is not None:
            self._console.print()
            self._console.print(Markdown(event.content))
            self._console.print()
        else:
            print(f"\n{event.content}\n")
```
关键改动：只在 `first_content_received == False` 时才渲染 final_answer。如果已经通过 stream_delta 输出了内容，就不再重复。

### Step 2: 重构思考展示为 Rich Panel
修改 `src/pc_assistant/ui/chat.py`：

新增 `_think_panel` 属性和更新逻辑：

```python
# __init__ 中新增
self._think_content = ""
self._think_live = None

# think_start — 创建 Live Panel
elif event.type == "think_start":
    self._spinner.stop()
    spinner_active = False
    self._think_content = ""
    if self._console is not None:
        from rich.live import Live
        from rich.text import Text
        panel = Panel(
            Text("💭 Thinking...", style="dim italic"),
            title="🧠",
            border_style="blue",
            width=80,
        )
        self._think_live = Live(panel, console=self._console, refresh_per_second=8)
        self._think_live.start()

# stream_think_delta — 更新 Panel 内容
elif event.type == "stream_think_delta":
    self._think_content += event.content
    if self._think_live is not None and self._console is not None:
        display_text = self._think_content[-200:]
        new_panel = Panel(
            Text(display_text, style="dim italic"),
            title="🧠",
            border_style="blue",
            width=80,
        )
        self._think_live.update(new_panel)

# think_end — 替换为折叠摘要
elif event.type == "think_end":
    if self._think_live is not None:
        self._think_live.stop()
        self._think_live = None
    elapsed = ...
    summary = self._think_content[:100].replace("\n", " ")
    if self._console is not None:
        collapsed = f"💭 Thought {elapsed:.1f}s | {summary}..."
        panel = Panel(collapsed, title="🧠", border_style="dim blue", width=80)
        self._console.print(panel)
    self._think_content = ""
```

### Step 3: 清理旧的 sys.stdout.write 路径
- 移除 `stream_think_delta` 中的 `sys.stdout.write`
- 移除 `stream_delta` 中的 `sys.stdout.write`（改为用 Rich console 输出）

### Step 4: 测试验证
- 运行完整测试套件
- CLI 手动测试：输入简单问题（无 think）和复杂问题（有 think），确认：
  - 无重复输出
  - Think 内容可见且美观
  - 状态栏正确

### Step 5: 提交推送
