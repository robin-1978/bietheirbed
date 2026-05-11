# 跨平台适配 + LLM API 支持 + TUI 美化 Spec

## Why
当前 Agent 硬编码了 Windows 特定逻辑（PowerShell、Windows 路径、Windows 安全规则），无法在 Ubuntu/macOS 上运行。LLM Provider 仅支持 llama.cpp 本地服务器，无法使用 OpenAI/Anthropic 等云端 API。TUI 界面缺少 Agent 状态面板，用户无法直观了解 Agent 运行状态。

## What Changes
- 引入平台抽象层，根据 OS 自动选择 Shell、路径格式、安全规则、应用启动方式
- **BREAKING**：`dangerous_commands` 和 `protected_paths` 默认值改为按平台动态生成
- LLM Provider 支持多种 API 后端：OpenAI、Anthropic、本地 llama.cpp，通过配置切换
- **BREAKING**：`AppConfig.llm_server_url` 改为 `AppConfig.llm_provider` + `AppConfig.llm_api_key` 等新字段
- TUI 新增状态栏：显示 LLM 连接状态、当前模型、对话轮次、Token 用量、Agent 状态
- TUI 新增 `/status` 命令：显示详细 Agent 状态

## Impact
- Affected specs: build-computer-assistant (LLM Provider、Shell 工具、安全规则、TUI)
- Affected code:
  - `src/pc_assistant/config.py` — 新增 LLM provider 配置字段
  - `src/pc_assistant/llm_provider.py` — 支持多 API 后端
  - `src/pc_assistant/tools/shell.py` — 平台感知的 Shell 执行
  - `src/pc_assistant/tools/application.py` — 平台感知的应用启动
  - `src/pc_assistant/tools/system.py` — 平台感知的磁盘路径
  - `src/pc_assistant/harness/safety.py` — 平台感知的安全规则
  - `src/pc_assistant/context/system_prompt.py` — 平台感知的系统提示词
  - `src/pc_assistant/ui/chat.py` — 状态栏 + 美化
  - `src/pc_assistant/agent.py` — Token 用量统计
  - `config/default.yaml` — 新配置格式
  - 对应测试文件

## ADDED Requirements

### Requirement: 平台抽象层
系统 SHALL 在启动时检测当前操作系统（Windows/macOS/Linux），并自动适配行为。

#### Scenario: Windows 平台
- **WHEN** 系统运行在 Windows 上
- **THEN** Shell 使用 PowerShell，路径使用反斜杠，安全规则包含 Windows 危险命令和受保护路径

#### Scenario: Linux 平台
- **WHEN** 系统运行在 Linux 上
- **THEN** Shell 使用 bash，路径使用正斜杠，安全规则包含 Linux 危险命令和受保护路径

#### Scenario: macOS 平台
- **WHEN** 系统运行在 macOS 上
- **THEN** Shell 使用 zsh，路径使用正斜杠，安全规则包含 macOS 危险命令和受保护路径

### Requirement: 平台感知的 Shell 工具
系统 SHALL 根据当前平台自动选择正确的 Shell 执行命令。

#### Scenario: Windows 执行命令
- **WHEN** 在 Windows 上执行 Shell 命令
- **THEN** 使用 `powershell -Command` 执行

#### Scenario: Linux/macOS 执行命令
- **WHEN** 在 Linux/macOS 上执行 Shell 命令
- **THEN** 使用 `/bin/bash -c` 或 `/bin/zsh -c` 执行

### Requirement: 平台感知的安全规则
系统 SHALL 根据当前平台提供不同的默认危险命令和受保护路径。

#### Scenario: Windows 安全规则
- **WHEN** 系统运行在 Windows 上
- **THEN** 危险命令包含 `del /s /q`、`format`、`rd /s` 等；受保护路径包含 `C:\Windows\System32`

#### Scenario: Linux 安全规则
- **WHEN** 系统运行在 Linux 上
- **THEN** 危险命令包含 `rm -rf /`、`mkfs`、`dd if=` 等；受保护路径包含 `/etc/passwd`、`/boot`

#### Scenario: macOS 安全规则
- **WHEN** 系统运行在 macOS 上
- **THEN** 危险命令包含 `rm -rf /`、`diskutil eraseDisk` 等；受保护路径包含 `/System`、`/Library`

### Requirement: 多 LLM API 后端支持
系统 SHALL 支持通过配置切换不同的 LLM API 后端。

#### Scenario: 使用 OpenAI API
- **WHEN** 配置 `llm_provider: "openai"` 并设置 `llm_api_key`
- **THEN** 系统使用 OpenAI API（https://api.openai.com/v1）发送请求，支持 GPT-4 等模型

#### Scenario: 使用 Anthropic API
- **WHEN** 配置 `llm_provider: "anthropic"` 并设置 `llm_api_key`
- **THEN** 系统使用 Anthropic API 发送请求，支持 Claude 等模型

#### Scenario: 使用本地 llama.cpp
- **WHEN** 配置 `llm_provider: "llamacpp"` 并设置 `llm_server_url`
- **THEN** 系统使用 llama.cpp OpenAI 兼容 API 发送请求（当前默认行为）

#### Scenario: 使用自定义 OpenAI 兼容 API
- **WHEN** 配置 `llm_provider: "openai_compatible"` 并设置 `llm_server_url` 和 `llm_api_key`
- **THEN** 系统使用自定义的 OpenAI 兼容 API 发送请求（如 vLLM、Ollama 等）

#### Scenario: API Key 缺失
- **WHEN** 配置了需要 API Key 的 provider 但未设置 `llm_api_key`
- **THEN** 系统启动时给出明确错误提示

### Requirement: TUI 状态栏
系统 SHALL 在 TUI 界面底部显示 Agent 状态信息。

#### Scenario: 状态栏显示
- **WHEN** TUI 界面运行
- **THEN** 界面顶部或底部显示状态栏，包含：LLM Provider 名称、模型名称、连接状态（🟢/🔴）、当前对话轮次、累计 Token 用量

#### Scenario: Agent 思考中
- **WHEN** Agent 正在处理请求
- **THEN** 状态栏显示 "Thinking..." 或 "Executing tool..." 状态

#### Scenario: Agent 空闲
- **WHEN** Agent 等待用户输入
- **THEN** 状态栏显示 "Ready" 状态

### Requirement: /status 命令
系统 SHALL 提供 `/status` 命令显示详细的 Agent 状态信息。

#### Scenario: 查看状态
- **WHEN** 用户输入 `/status`
- **THEN** 系统显示：LLM Provider、模型名称、连接状态、对话轮次、Token 用量、当前平台、工作目录、已注册工具列表

## MODIFIED Requirements

### Requirement: LLM Provider Layer
系统 SHALL 支持多种 LLM API 后端（OpenAI、Anthropic、llama.cpp、OpenAI 兼容），通过配置切换。保留原有的 chat completion 和 function calling 支持，新增 Anthropic 的 tool_use 格式适配。

#### Scenario: 成功连接 OpenAI API
- **WHEN** 配置了 OpenAI provider 和 API Key
- **THEN** 系统能成功发送 chat completion 请求并接收响应

#### Scenario: Anthropic tool_use 适配
- **WHEN** 使用 Anthropic provider 且 Agent 需要调用工具
- **THEN** 系统将 OpenAI function calling 格式转换为 Anthropic tool_use 格式发送，并将 Anthropic 响应转换回内部格式

### Requirement: 工具系统 - Shell 命令执行
系统 SHALL 提供平台感知的 Shell 命令执行工具，根据操作系统自动选择 Shell 类型。

#### Scenario: 执行普通命令
- **WHEN** Agent 调用 shell 工具并指定命令
- **THEN** 系统在当前平台对应的 Shell 中执行命令并返回 stdout 和 stderr

### Requirement: 终端聊天界面
系统 SHALL 提供增强的终端聊天界面，包含状态栏、Agent 状态指示和流式输出。

#### Scenario: 启动聊天
- **WHEN** 用户运行主程序
- **THEN** 系统显示欢迎信息、状态栏和提示符，等待用户输入

#### Scenario: 状态栏更新
- **WHEN** Agent 状态变化（开始思考、调用工具、返回结果）
- **THEN** 状态栏实时更新显示当前状态

## REMOVED Requirements
无
