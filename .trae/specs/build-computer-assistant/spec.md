# 电脑助手 Agent Spec

## Why
用户需要一个基于本地 Qwen 3.5 4B 模型的实用电脑助手，能通过自然语言对话完成电脑上的所有任务，而非一个 demo 级别的玩具。当前缺乏一个集成了先进提示词工程、上下文工程和 Harness 工程的本地 Agent 系统。

## What Changes
- 构建基于 ReAct 范式的 Agent 核心循环（Thought → Action → Observation）
- 通过 llama.cpp OpenAI 兼容 API 连接本地 Qwen 3.5 4B 模型
- 实现完整的工具系统：文件系统、Shell 执行、应用控制、网页浏览、系统信息、剪贴板、截图
- 实现上下文工程系统：动态上下文管理、对话历史摘要、工作记忆、工具输出管理
- 实现 Harness 工程系统：安全护栏、迭代限制、错误恢复、日志可观测性
- 实现终端聊天界面，支持流式输出和富文本格式
- 完整的单元测试和端到端测试

## Impact
- Affected specs: 无已有 spec，全新项目
- Affected code: 全新代码库 `c:\agent\`

## ADDED Requirements

### Requirement: LLM Provider Layer
系统 SHALL 通过 llama.cpp 的 OpenAI 兼容 API 连接本地 Qwen 3.5 4B 模型，支持 chat completion 和 function calling。

#### Scenario: 成功连接本地模型
- **WHEN** 系统启动并配置了正确的 llama.cpp server 地址
- **THEN** 系统能成功发送 chat completion 请求并接收响应

#### Scenario: Function Calling 支持
- **WHEN** Agent 决定需要调用工具
- **THEN** LLM 返回结构化的工具调用请求（工具名 + 参数），系统能正确解析并执行

#### Scenario: 模型不可用
- **WHEN** llama.cpp server 未启动或不可达
- **THEN** 系统向用户返回清晰的错误提示，而非崩溃

### Requirement: ReAct Agent Core Loop
系统 SHALL 实现 ReAct（Reasoning + Acting）范式的 Agent 核心循环，支持多步推理和工具调用。

#### Scenario: 简单任务直接回答
- **WHEN** 用户提出不需要工具的问题（如"什么是Python？"）
- **THEN** Agent 直接生成回答，不调用任何工具

#### Scenario: 需要工具的任务
- **WHEN** 用户提出需要工具的任务（如"帮我查看当前目录下的文件"）
- **THEN** Agent 执行 Thought → Action → Observation 循环，调用适当工具并返回结果

#### Scenario: 多步任务
- **WHEN** 用户提出需要多步操作的任务（如"找到所有 PDF 文件并移动到新文件夹"）
- **THEN** Agent 能规划并执行多个工具调用步骤，每步基于前步结果

#### Scenario: 迭代限制
- **WHEN** Agent 循环超过最大迭代次数（默认 15）
- **THEN** 系统终止循环并告知用户任务未完成的原因

### Requirement: 工具系统 - 文件系统操作
系统 SHALL 提供文件系统操作工具，包括：读取文件、写入文件、列出目录、搜索文件、创建目录、删除文件/目录、移动/重命名文件。

#### Scenario: 读取文件
- **WHEN** Agent 调用 read_file 工具并指定路径
- **THEN** 系统返回文件内容（对大文件截断并提示）

#### Scenario: 写入文件
- **WHEN** Agent 调用 write_file 工具并指定路径和内容
- **THEN** 系统创建或覆盖文件并返回成功确认

#### Scenario: 列出目录
- **WHEN** Agent 调用 list_directory 工具
- **THEN** 系统返回目录内容列表（文件名、大小、修改时间）

#### Scenario: 搜索文件
- **WHEN** Agent 调用 search_files 工具并指定模式
- **THEN** 系统返回匹配文件路径列表

### Requirement: 工具系统 - Shell 命令执行
系统 SHALL 提供 Shell 命令执行工具，支持运行 PowerShell 命令并获取输出。

#### Scenario: 执行普通命令
- **WHEN** Agent 调用 run_shell 工具并指定命令
- **THEN** 系统在 PowerShell 中执行命令并返回 stdout 和 stderr

#### Scenario: 危险命令拦截
- **WHEN** Agent 尝试执行危险命令（如 rm -rf /、format 等）
- **THEN** 系统拦截并要求用户确认，用户拒绝则不执行

#### Scenario: 命令超时
- **WHEN** Shell 命令执行超过超时时间（默认 30 秒）
- **THEN** 系统终止进程并返回超时提示

### Requirement: 工具系统 - 应用控制
系统 SHALL 提供应用控制工具，包括：打开应用、关闭应用、列出运行中的进程。

#### Scenario: 打开应用
- **WHEN** Agent 调用 open_application 工具并指定应用名
- **THEN** 系统启动对应应用

#### Scenario: 列出进程
- **WHEN** Agent 调用 list_processes 工具
- **THEN** 系统返回当前运行进程列表（PID、名称、内存占用）

### Requirement: 工具系统 - 网页浏览
系统 SHALL 提供网页浏览工具，包括：网页搜索、获取网页内容。

#### Scenario: 网页搜索
- **WHEN** Agent 调用 web_search 工具并指定查询
- **THEN** 系统返回搜索结果列表（标题、URL、摘要）

#### Scenario: 获取网页内容
- **WHEN** Agent 调用 fetch_webpage 工具并指定 URL
- **THEN** 系统返回网页的文本内容（Markdown 格式）

### Requirement: 工具系统 - 系统信息
系统 SHALL 提供系统信息工具，包括：获取系统信息（OS、CPU、内存、磁盘）、获取当前日期时间。

#### Scenario: 获取系统信息
- **WHEN** Agent 调用 get_system_info 工具
- **THEN** 系统返回操作系统版本、CPU 使用率、内存使用率、磁盘空间等信息

### Requirement: 工具系统 - 剪贴板操作
系统 SHALL 提供剪贴板操作工具，包括：读取剪贴板、写入剪贴板。

#### Scenario: 读取剪贴板
- **WHEN** Agent 调用 read_clipboard 工具
- **THEN** 系统返回剪贴板当前文本内容

### Requirement: 工具系统 - 截图
系统 SHALL 提供截图工具，捕获屏幕内容并保存为文件。

#### Scenario: 截取屏幕
- **WHEN** Agent 调用 take_screenshot 工具
- **THEN** 系统截取当前屏幕并保存到指定路径，返回文件路径

### Requirement: 上下文工程系统
系统 SHALL 实现上下文工程，动态管理 Agent 的上下文窗口内容。

#### Scenario: 系统提示词构建
- **WHEN** Agent 开始新的对话轮次
- **THEN** 系统构建包含角色定义、可用工具描述、安全规则、当前工作目录的系统提示词

#### Scenario: 对话历史管理
- **WHEN** 对话历史超过上下文窗口限制
- **THEN** 系统自动摘要早期对话，保留近期完整对话和摘要

#### Scenario: 工具输出管理
- **WHEN** 工具返回大量输出
- **THEN** 系统自动截断输出至合理长度，保留关键信息

#### Scenario: 工作记忆
- **WHEN** Agent 在多步任务中需要记住中间状态
- **THEN** 系统维护一个工作记忆区域，Agent 可主动读写

### Requirement: Harness 工程系统
系统 SHALL 实现 Harness 工程，提供生产级管控能力。

#### Scenario: 安全护栏 - 危险操作确认
- **WHEN** Agent 尝试执行潜在危险操作（删除文件、执行危险命令）
- **THEN** 系统暂停执行，向用户展示操作详情并请求确认

#### Scenario: 安全护栏 - 路径限制
- **WHEN** Agent 尝试访问系统关键路径（如 C:\Windows\System32）
- **THEN** 系统拦截并警告，需用户确认

#### Scenario: 错误恢复
- **WHEN** 工具执行失败
- **THEN** Agent 收到错误信息并尝试自我修正（如换一种方式完成任务）

#### Scenario: 日志记录
- **WHEN** Agent 执行任何操作
- **THEN** 系统记录完整的操作日志（时间戳、操作类型、参数、结果）

#### Scenario: 可观测性
- **WHEN** 用户查看 Agent 的思考过程
- **THEN** 系统展示 Agent 的 Thought、Action、Observation 完整链路

### Requirement: 终端聊天界面
系统 SHALL 提供终端聊天界面，支持流式输出和富文本格式。

#### Scenario: 启动聊天
- **WHEN** 用户运行主程序
- **THEN** 系统显示欢迎信息和提示符，等待用户输入

#### Scenario: 流式输出
- **WHEN** Agent 生成回复
- **THEN** 系统逐 token 流式显示，而非等待完整生成

#### Scenario: 工具调用展示
- **WHEN** Agent 调用工具
- **THEN** 界面清晰展示工具名称、参数和执行结果

#### Scenario: 退出
- **WHEN** 用户输入 /exit 或 /quit
- **THEN** 系统保存对话历史并优雅退出

### Requirement: 单元测试
系统 SHALL 为所有核心模块提供单元测试，测试覆盖率不低于 80%。

#### Scenario: 工具测试
- **WHEN** 运行 pytest
- **THEN** 每个工具的输入解析、执行逻辑、输出格式均有测试覆盖

#### Scenario: Agent 循环测试
- **WHEN** 运行 pytest
- **THEN** Agent 核心循环的各种路径（直接回答、单步工具、多步工具、错误恢复）均有测试

### Requirement: 端到端测试
系统 SHALL 提供端到端测试，验证完整的用户场景。

#### Scenario: 文件操作端到端
- **WHEN** 运行端到端测试
- **THEN** 验证"创建文件 → 读取文件 → 修改文件 → 删除文件"完整流程

#### Scenario: 多步任务端到端
- **WHEN** 运行端到端测试
- **THEN** 验证"搜索文件 → 分析内容 → 生成报告"完整流程

## MODIFIED Requirements
无

## REMOVED Requirements
无
