# 修复 LLM 超时问题 — 计划文档

## 问题分析

llama.cpp 日志显示服务器在 prompt processing 到 86.5% 时触发 `should_stop` 超时：

```
slot update_slots: id  1 | task 1860 | n_tokens = 3319, ...
srv          next: stopping wait for next result due to should_stop condition
srv          stop: cancel task, id_task = 1860
```

根因有三：

1. **Prompt 过大**：3319 tokens，叠加 7 个工具 schema + Memory Rules + 对话历史，4B 模型处理缓慢
2. **超时时间不可配置**：`LLMProvider` 硬编码 120s，`AppConfig` 没有 `llm_timeout` 字段
3. **System Prompt 冗长**：Memory Rules 段落过于 verbose，每次请求都重复发送

## 修复步骤

### Step 1: 添加 LLM 超时配置

修改 `src/pc_assistant/config.py`：
- 在 `AppConfig` 添加 `llm_timeout: float = 120.0` 字段
- 在 `_env_overrides()` 添加 `PC_LLM_TIMEOUT` 环境变量映射
- 同步更新 `config/default.yaml`（如存在）

修改 `src/pc_assistant/agent.py`：
- `Agent.__init__()` 中初始化 `LLMProvider` 时传入 `timeout=self._config.llm_timeout`

### Step 2: 精简 System Prompt

修改 `src/pc_assistant/context/system_prompt.py`：
- 将 Memory Rules 从多行 verbose 格式压缩为简洁的 bullet points
- 去掉英文示例，改为通用说明（中英双语均可识别）
- 保持语义完整但减少 token 数量

### Step 3: 优化 Agent 中的超时/错误处理

修改 `src/pc_assistant/agent.py`：
- 在 `run()` 的 `try/except` 块中，区分 `httpx.TimeoutException` 与其他异常
- 当检测到超时时，yield 一个友好的 `error` event，提示用户可能原因（prompt 太长、模型忙等）
- 不要直接 crash，让用户可以继续对话

### Step 4: 运行测试并验证

- 运行 `pytest` 确保全部 303 个测试通过
- 检查是否有新的 type/lint 错误

## 预期效果

- Prompt token 数量下降 10~15%，减轻 4B 模型负担
- 用户可通过 `PC_LLM_TIMEOUT=300` 或修改 YAML 自定义超时
- 超时后 UI 显示友好提示，而非静默失败或 raw exception
