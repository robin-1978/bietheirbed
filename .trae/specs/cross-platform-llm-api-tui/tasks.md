# Tasks

- [ ] Task 1: 创建平台抽象模块 `src/pc_assistant/platform_.py`
  - [ ] SubTask 1.1: 实现 `get_platform()` 函数，返回 "windows"/"linux"/"macos"
  - [ ] SubTask 1.2: 实现 `get_shell_command()` 函数，根据平台返回 Shell 执行命令前缀（Windows: `powershell -Command`，Linux: `/bin/bash -c`，macOS: `/bin/zsh -c`）
  - [ ] SubTask 1.3: 实现 `get_default_dangerous_commands()` 函数，按平台返回默认危险命令列表
  - [ ] SubTask 1.4: 实现 `get_default_protected_paths()` 函数，按平台返回默认受保护路径列表
  - [ ] SubTask 1.5: 实现 `get_path_separator()` 和 `normalize_path()` 辅助函数
  - [ ] SubTask 1.6: 编写平台抽象模块单元测试（mock platform.system）

- [ ] Task 2: 改造 Shell 工具为平台感知
  - [ ] SubTask 2.1: 修改 `ShellTool._run()` 使用 `get_shell_command()` 构建执行命令
  - [ ] SubTask 2.2: Windows 使用 `asyncio.create_subprocess_exec("powershell", "-Command", command)` 替代 `create_subprocess_shell`
  - [ ] SubTask 2.3: Linux/macOS 使用 `asyncio.create_subprocess_exec("/bin/bash", "-c", command)`
  - [ ] SubTask 2.4: 编写 Shell 工具跨平台测试

- [ ] Task 3: 改造安全规则为平台感知
  - [ ] SubTask 3.1: 修改 `SafetyChecker.__init__()` 使用 `get_default_dangerous_commands()` 和 `get_default_protected_paths()` 作为默认值
  - [ ] SubTask 3.2: 修改 `AppConfig` 的 `dangerous_commands` 和 `protected_paths` 默认值使用平台感知函数
  - [ ] SubTask 3.3: 编写安全规则跨平台测试

- [ ] Task 4: 改造应用控制工具为平台感知
  - [ ] SubTask 4.1: 修改 `ApplicationTool._launch()` 的 Windows 分支使用 `DETACHED_PROCESS`，Linux 使用 `start_new_session=True`，macOS 使用 `open` 命令
  - [ ] SubTask 4.2: 修改 `SystemTool._disk_usage()` 的路径逻辑，Linux 使用 `/` 而非 drive letter
  - [ ] SubTask 4.3: 编写应用控制工具跨平台测试

- [ ] Task 5: 改造系统提示词为平台感知
  - [ ] SubTask 5.1: 修改 `build_system_prompt()` 使用平台抽象模块获取 OS 信息和 Shell 类型
  - [ ] SubTask 5.2: 在提示词中明确告知 Agent 当前 Shell 类型（如 "Current shell: PowerShell" 或 "Current shell: bash"）

- [ ] Task 6: 扩展 LLM Provider 支持多 API 后端
  - [ ] SubTask 6.1: 修改 `AppConfig`，新增 `llm_provider` 字段（枚举：llamacpp/openai/anthropic/openai_compatible），新增 `llm_api_key`、`llm_api_base` 字段
  - [ ] SubTask 6.2: 修改 `LLMProvider.__init__()` 根据 provider 类型设置不同的 base_url 和 headers
  - [ ] SubTask 6.3: OpenAI provider：设置 `base_url=https://api.openai.com/v1`，headers 添加 `Authorization: Bearer {api_key}`
  - [ ] SubTask 6.4: Anthropic provider：实现 Anthropic API 适配层（转换 tools schema 格式、转换 tool_use 响应格式）
  - [ ] SubTask 6.5: OpenAI Compatible provider：使用自定义 `llm_api_base` + 可选 `llm_api_key`
  - [ ] SubTask 6.6: 启动时检查 API Key 是否配置（需要 Key 的 provider 缺少 Key 时报错）
  - [ ] SubTask 6.7: 编写 LLM Provider 多后端测试

- [ ] Task 7: Agent Token 用量统计
  - [ ] SubTask 7.1: 在 `Agent` 中添加 `total_tokens` 和 `total_iterations` 计数器
  - [ ] SubTask 7.2: 在每次 LLM 响应后累加 `usage.prompt_tokens` 和 `usage.completion_tokens`
  - [ ] SubTask 7.3: 暴露 `agent.get_status()` 方法，返回当前状态字典（provider、model、tokens、iterations、platform 等）

- [ ] Task 8: TUI 状态栏实现
  - [ ] SubTask 8.1: 在 `ChatUI` 中添加 `_render_status_bar()` 方法，使用 Rich 渲染状态栏
  - [ ] SubTask 8.2: 状态栏显示：Provider 名称 | 模型名称 | 连接状态 🟢/🔴 | 对话轮次 | Token 用量 | Agent 状态
  - [ ] SubTask 8.3: 在每次事件处理后更新状态栏
  - [ ] SubTask 8.4: 在欢迎信息下方显示初始状态栏

- [ ] Task 9: TUI /status 命令
  - [ ] SubTask 9.1: 在 `_handle_user_command()` 中添加 `/status` 命令处理
  - [ ] SubTask 9.2: 调用 `agent.get_status()` 获取状态，使用 Rich Table 展示
  - [ ] SubTask 9.3: 更新 `/help` 命令的命令列表

- [ ] Task 10: 更新配置文件
  - [ ] SubTask 10.1: 更新 `config/default.yaml`，添加 `llm_provider`、`llm_api_key`、`llm_api_base` 字段
  - [ ] SubTask 10.2: 更新 `_env_overrides()`，添加 `PC_LLM_PROVIDER`、`PC_LLM_API_KEY`、`PC_LLM_API_BASE` 环境变量映射
  - [ ] SubTask 10.3: 编写配置模块测试

- [ ] Task 11: 端到端验证
  - [ ] SubTask 11.1: 在 Windows 上运行完整测试套件
  - [ ] SubTask 11.2: 验证平台抽象模块在 mock Linux/macOS 下的行为
  - [ ] SubTask 11.3: 验证 LLM Provider 多后端配置加载
  - [ ] SubTask 11.4: 验证 TUI 状态栏和 /status 命令

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1]
- [Task 5] depends on [Task 1]
- [Task 6] depends on [Task 10]
- [Task 7] depends on [Task 6]
- [Task 8] depends on [Task 7]
- [Task 9] depends on [Task 7]
- Task 2, 3, 4, 5 可并行开发
- Task 8, 9 可并行开发
