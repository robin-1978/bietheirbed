# Tasks

- [x] Task 1: 项目骨架搭建 - 创建项目结构、依赖管理、配置系统
  - [x] SubTask 1.1: 创建项目目录结构（src/pc_assistant/, tests/, config/）
  - [x] SubTask 1.2: 创建 pyproject.toml，定义依赖（httpx, pydantic, rich, pytest 等）
  - [x] SubTask 1.3: 创建配置模块 config.py，支持 YAML 配置文件和环境变量
  - [x] SubTask 1.4: 创建日志模块 logger.py，支持文件日志和控制台日志

- [x] Task 2: LLM Provider 层实现 - 连接 llama.cpp server 的 OpenAI 兼容 API
  - [x] SubTask 2.1: 实现 LLMProvider 类，封装 chat completion API 调用（httpx 异步客户端）
  - [x] SubTask 2.2: 实现 function calling 消息格式构建（tools schema → OpenAI 格式）
  - [x] SubTask 2.3: 实现流式响应处理（SSE 解析）
  - [x] SubTask 2.4: 实现连接健康检查和错误重试机制
  - [x] SubTask 2.5: 编写 LLM Provider 单元测试

- [x] Task 3: 工具系统实现 - 定义工具基类和注册机制
  - [x] SubTask 3.1: 实现 ToolBase 基类（名称、描述、参数 schema、执行方法、安全等级）
  - [x] SubTask 3.2: 实现 ToolRegistry 工具注册中心（注册、查询、按名称调用）
  - [x] SubTask 3.3: 实现 OpenAI function calling schema 自动生成
  - [x] SubTask 3.4: 编写工具基类和注册中心单元测试

- [x] Task 4: 文件系统工具实现
  - [x] SubTask 4.1: 实现 read_file 工具（支持编码检测、大文件截断）
  - [x] SubTask 4.2: 实现 write_file 工具（支持创建目录、覆盖确认）
  - [x] SubTask 4.3: 实现 list_directory 工具（文件名、大小、类型、修改时间）
  - [x] SubTask 4.4: 实现 search_files 工具（glob 模式匹配、递归搜索）
  - [x] SubTask 4.5: 实现 create_directory 工具
  - [x] SubTask 4.6: 实现 delete_file 工具（安全确认）
  - [x] SubTask 4.7: 实现 move_file 工具（移动/重命名）
  - [x] SubTask 4.8: 编写文件系统工具单元测试

- [x] Task 5: Shell 执行工具实现
  - [x] SubTask 5.1: 实现 run_shell 工具（PowerShell 执行、stdout/stderr 捕获、超时控制）
  - [x] SubTask 5.2: 实现危险命令检测和拦截机制
  - [x] SubTask 5.3: 编写 Shell 执行工具单元测试

- [x] Task 6: 应用控制工具实现
  - [x] SubTask 6.1: 实现 open_application 工具（通过应用名或路径启动）
  - [x] SubTask 6.2: 实现 list_processes 工具（进程名、PID、内存占用）
  - [x] SubTask 6.3: 实现 kill_process 工具（安全确认）
  - [x] SubTask 6.4: 编写应用控制工具单元测试

- [x] Task 7: 网页浏览工具实现
  - [x] SubTask 7.1: 实现 web_search 工具（调用搜索引擎 API 或爬取搜索页）
  - [x] SubTask 7.2: 实现 fetch_webpage 工具（HTTP GET + HTML 转 Markdown）
  - [x] SubTask 7.3: 编写网页浏览工具单元测试

- [x] Task 8: 系统信息和剪贴板工具实现
  - [x] SubTask 8.1: 实现 get_system_info 工具（OS、CPU、内存、磁盘）
  - [x] SubTask 8.2: 实现 get_datetime 工具
  - [x] SubTask 8.3: 实现 read_clipboard / write_clipboard 工具
  - [x] SubTask 8.4: 实现 take_screenshot 工具（Pillow + mss）
  - [x] SubTask 8.5: 编写系统信息和剪贴板工具单元测试

- [x] Task 9: 上下文工程系统实现
  - [x] SubTask 9.1: 实现 SystemPromptBuilder（角色定义、工具描述注入、安全规则、当前状态）
  - [x] SubTask 9.2: 实现 ConversationManager（对话历史管理、自动摘要、上下文窗口预算分配）
  - [x] SubTask 9.3: 实现 WorkingMemory（Agent 可读写的键值存储，跨轮次持久化）
  - [x] SubTask 9.4: 实现 ToolOutputTruncator（大输出截断策略，保留首尾关键信息）
  - [x] SubTask 9.5: 编写上下文工程系统单元测试

- [x] Task 10: Harness 工程系统实现
  - [x] SubTask 10.1: 实现 SafetyGuardrail（危险操作检测、路径限制、用户确认流程）
  - [x] SubTask 10.2: 实现 IterationLimiter（最大迭代次数、单步超时）
  - [x] SubTask 10.3: 实现 ErrorRecovery（工具执行失败重试、Agent 自我修正提示）
  - [x] SubTask 10.4: 实现 AuditLogger（操作审计日志，JSON 格式，可查询）
  - [x] SubTask 10.5: 编写 Harness 工程系统单元测试

- [x] Task 11: ReAct Agent 核心循环实现
  - [x] SubTask 11.1: 实现 Agent 类（初始化 LLM Provider、ToolRegistry、ContextManager、Harness）
  - [x] SubTask 11.2: 实现 ReAct 循环：解析 LLM 响应 → 判断是否工具调用 → 执行工具 → 注入观察结果 → 继续循环
  - [x] SubTask 11.3: 实现工具调用解析（从 LLM 响应提取工具名和参数）
  - [x] SubTask 11.4: 实现最终回答生成（当 LLM 不再调用工具时）
  - [x] SubTask 11.5: 编写 Agent 核心循环单元测试

- [x] Task 12: 终端聊天界面实现
  - [x] SubTask 12.1: 实现 ChatUI 类（Rich 库，Markdown 渲染，语法高亮）
  - [x] SubTask 12.2: 实现流式输出显示（逐 token 显示 Agent 思考和回答）
  - [x] SubTask 12.3: 实现工具调用可视化（展示工具名、参数、执行状态、结果摘要）
  - [x] SubTask 12.4: 实现用户命令处理（/exit, /clear, /history, /tools, /help）
  - [x] SubTask 12.5: 实现安全确认交互（危险操作时弹出确认提示）

- [x] Task 13: 主程序入口和集成
  - [x] SubTask 13.1: 实现 main.py 入口（参数解析、配置加载、组件初始化、启动聊天循环）
  - [x] SubTask 13.2: 实现默认配置文件 config.yaml
  - [x] SubTask 13.3: 实现优雅退出（保存对话历史、清理资源）

- [x] Task 14: 端到端测试
  - [x] SubTask 14.1: 实现文件操作端到端测试（创建→读取→修改→删除）
  - [x] SubTask 14.2: 实现多步任务端到端测试（搜索文件→分析→生成报告）
  - [x] SubTask 14.3: 实现安全护栏端到端测试（危险操作拦截确认）
  - [x] SubTask 14.4: 实现错误恢复端到端测试（工具失败后 Agent 自我修正）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 3]
- [Task 5] depends on [Task 3]
- [Task 6] depends on [Task 3]
- [Task 7] depends on [Task 3]
- [Task 8] depends on [Task 3]
- [Task 9] depends on [Task 1]
- [Task 10] depends on [Task 1]
- [Task 11] depends on [Task 2, Task 3, Task 9, Task 10]
- [Task 12] depends on [Task 11]
- [Task 13] depends on [Task 11, Task 12]
- [Task 14] depends on [Task 13]
- Task 4-8 可并行开发
