# 修复 Token 计数 + CLI 界面优化 — 计划文档

## 一、Token 计数修复

### 根因

`chat_stream()` 的 payload **缺少 `stream_options` 参数**。OpenAI 和 llama.cpp 从 2024 年起要求流式请求显式传入 `stream_options: {"include_usage": true}` 才会在最后一个 chunk 返回 `usage` 字段。没有这个参数，`chunk.usage` 始终为空字典 `{}`，token 计数永远为 0。

### 修复步骤

#### Step 1: payload 添加 stream_options

修改 `src/pc_assistant/llm_provider.py`：
- `chat_stream()` 的 payload 中添加 `"stream_options": {"include_usage": True}`
- 兼容性：旧版 llama.cpp 会忽略不认识的字段，不会报错

#### Step 2: 补充 token 计数测试

修改 `tests/test_llm_provider.py`：
- 添加 `test_chat_stream_with_usage` 测试，验证 SSE 流中包含 usage 时能正确提取

修改 `tests/test_agent.py`：
- 添加 `test_token_counting` 测试，验证 agent 能正确累加 prompt/completion tokens

---

## 二、CLI 界面优化

### 当前设计评审

| 组件 | 当前状态 | 问题 |
|------|---------|------|
| 状态栏 | Panel 包裹，显示 provider/model/status/turns/tokens/memory | Panel 每次输入都重新渲染，占用垂直空间；信息密度可提升 |
| 工具调用 | Panel 展示工具名+完整参数 JSON | ✅ 设计不错，但参数 JSON 可能很长，占屏 |
| 工具结果 | 单行 `← name: truncated` | 信息太少，看不出结果类型；成功/失败区分不够明显 |
| Thinking | dim italic + sys.stdout 流式输出 | ✅ 已优化，体验良好 |
| 最终回答 | 流式输出 + Markdown 渲染 | ✅ 设计合理 |
| 用户输入 | `You>` 绿色粗体 | ✅ 简洁清晰 |
| 错误/警告 | ✗/⚠ 前缀 + 红/黄色 | ✅ 直观 |
| 欢迎界面 | ASCII art + 版本号 | ✅ 经典风格 |

### 优化方案

#### Step 3: 状态栏改为紧凑单行

当前状态栏用 Panel 包裹，每次输入都渲染一个带边框的 Panel，占用 3 行垂直空间。改为**紧凑单行**：

```
 🟢 llamacpp | qwen3.5 | ready | 3 turns | 1.2k tokens | 🧠 5
```

- 去掉 Panel 边框，改用 `Text` 单行渲染
- token 数量用 `1.2k` 格式（>999 时缩写）
- 状态用颜色区分：ready=绿, thinking=蓝, executing_xxx=黄

#### Step 4: 工具调用展示优化

当前工具调用展示完整 JSON 参数，可能很长。优化为：
- **单行摘要**：工具名 + 关键参数（只取前 2 个参数的值）
- **可折叠详情**：如果参数超过 3 个或总长度超过 80 字符，只显示摘要，完整参数用 dim 样式折叠在下方

示例：
```
 🔧 web → url="https://example.com"
   (2 more params...)
```

替代当前的：
```
╭────────── 🔧 web ──────────╮
│ {                          │
│   "url": "https://...",    │
│   "method": "GET",         │
│   "headers": {}            │
│ }                          │
╰────────────────────────────╯
```

#### Step 5: 工具结果展示增强

当前工具结果只有一行 `← name: truncated`，优化为：
- 成功：`  ✅ web → 200 OK (1.2kB)` — 显示状态码/大小
- 错误：`  ❌ web → Connection refused` — 红色高亮
- 截断提示更明确：`... (showing 500/2048 chars)`

#### Step 6: 最终回答分隔线

在 AI 回答前添加一条细分隔线，让对话层次更清晰：

```
────────────────────────────────
AI> 这是回答内容...
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `src/pc_assistant/llm_provider.py` | payload 添加 `stream_options` |
| `src/pc_assistant/ui/chat.py` | 状态栏/工具调用/工具结果/分隔线优化 |
| `tests/test_llm_provider.py` | 添加 usage 流式测试 |
| `tests/test_agent.py` | 添加 token 累加测试 |

## 执行顺序

1. Step 1: 修复 token 计数（添加 stream_options）
2. Step 2: 补充 token 计数测试
3. Step 3: 状态栏优化
4. Step 4: 工具调用展示优化
5. Step 5: 工具结果展示增强
6. Step 6: 最终回答分隔线
7. 运行全部测试验证
