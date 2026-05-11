# 修复计划：ReAct 死循环 + 系统提示词优化 + 推送 GitHub

## 问题分析

### 问题1：Agent 卡在工具调用循环中
用户问"今天是几号"，Agent 不直接回答，而是调用 system(info) → shell(date) → 可能继续调用更多工具。

**根本原因**：
1. **系统提示词缺少当前日期**：模型不知道今天日期，所以必须调用工具来获取
2. **系统提示词没有明确指导何时不用工具**：小模型（4B）无法判断简单问题不需要工具
3. **没有死循环检测**：即使模型反复调用相同工具，也没有机制打断

### 问题2：没有死循环防护
当前只有 `max_iterations=15` 的硬限制，但缺少：
- 重复工具调用检测（相同工具+相同参数）
- 连续无进展检测
- 强制终止后给用户有用的反馈

### 问题3：流式输出时 think 标签处理有 bug
`stream_delta` 事件直接输出 `chunk.delta_content`，包括 `<think...>` 标签内容。
用户在终端看到了原始的 think 标签文本。

## 修复步骤

### Step 1: 系统提示词注入当前日期和关键上下文
修改 `build_system_prompt()` 和 `Agent.__init__()`：
- 在系统提示词中注入当前日期时间（"今天是 2026年5月11日"）
- 注入当前工作目录
- 添加明确的工具使用指导："对于你已知的信息（如当前日期、基本常识），直接回答，不要调用工具"
- 添加"只用必要的工具，不要重复调用同一工具"的规则

### Step 2: Agent 添加死循环检测
在 `Agent.run()` 的循环中添加：
- **重复调用检测**：记录最近 N 次工具调用（tool_name + args hash），如果重复则打断
- **连续无进展检测**：如果连续 2 次工具调用结果没有带来新信息，强制终止
- 当检测到死循环时，yield `iteration_limit` 事件并附带已收集的信息

### Step 3: 修复流式输出 think 标签泄漏
修改 `stream_delta` 事件的内容过滤：
- 在流式输出过程中，累积文本并实时检测 think 标签
- 只输出 think 标签之外的文本
- think 标签内的文本不发送给 UI

### Step 4: 降低 max_iterations 默认值
将 `max_iterations` 从 15 降为 8。对于 4B 模型，15 步太多了。
8 步已经足够完成复杂的多步任务。

### Step 5: 推送代码到 GitHub
```bash
git remote add origin https://github.com/Robin-1978/BieTheirBed.git
git push -u origin main
```

## 涉及文件
1. `src/pc_assistant/context/system_prompt.py` — 注入日期、优化提示词
2. `src/pc_assistant/agent.py` — 死循环检测、think 标签过滤修复
3. `src/pc_assistant/config.py` — max_iterations 默认值调整
4. `config/default.yaml` — 配置同步
5. `tests/test_agent.py` — 新增死循环检测测试
