* [x] 项目骨架搭建完成：目录结构、pyproject.toml、配置模块、日志模块均可正常工作

* [x] LLM Provider 能成功连接 llama.cpp server 并完成 chat completion 调用

* [x] LLM Provider 支持 function calling 消息格式，能正确发送 tools schema 并解析工具调用响应

* [x] LLM Provider 支持流式响应（SSE），能逐 token 输出

* [x] 工具基类 ToolBase 和注册中心 ToolRegistry 实现完整，能自动生成 OpenAI function calling schema

* [x] 文件系统工具全部实现：read\_file, write\_file, list\_directory, search\_files, create\_directory, delete\_file, move\_file

* [x] Shell 执行工具实现：run\_shell 支持 PowerShell 执行、超时控制、危险命令拦截

* [x] 应用控制工具实现：open\_application, list\_processes, kill\_process

* [x] 网页浏览工具实现：web\_search, fetch\_webpage

* [x] 系统信息和剪贴板工具实现：get\_system\_info, get\_datetime, read\_clipboard, write\_clipboard, take\_screenshot

* [x] 上下文工程系统实现：SystemPromptBuilder 动态构建系统提示词

* [x] 上下文工程系统实现：ConversationManager 支持对话历史管理和自动摘要

* [x] 上下文工程系统实现：WorkingMemory 支持跨轮次键值存储

* [x] 上下文工程系统实现：ToolOutputTruncator 能截断大输出保留关键信息

* [x] Harness 工程系统实现：SafetyGuardrail 能检测危险操作并要求用户确认

* [x] Harness 工程系统实现：IterationLimiter 限制最大迭代次数

* [x] Harness 工程系统实现：ErrorRecovery 支持工具失败后 Agent 自我修正

* [x] Harness 工程系统实现：AuditLogger 记录完整操作审计日志

* [x] ReAct Agent 核心循环实现：能正确处理直接回答、单步工具调用、多步工具调用

* [x] ReAct Agent 能解析 LLM 的工具调用响应并正确执行对应工具

* [x] 终端聊天界面实现：支持流式输出、Markdown 渲染、工具调用可视化

* [x] 终端聊天界面支持用户命令：/exit, /clear, /history, /tools, /help

* [x] 终端聊天界面支持安全确认交互

* [x] 主程序入口 main.py 能正常启动、加载配置、初始化组件、运行聊天循环

* [x] 单元测试覆盖率不低于 80%，所有测试通过（219 tests, 82.39% coverage）

* [x] 端到端测试：文件操作完整流程测试通过

* [x] 端到端测试：多步任务完整流程测试通过

* [x] 端到端测试：安全护栏拦截测试通过

* [x] 端到端测试：错误恢复测试通过

