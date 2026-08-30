# 大模型 / Agent 应用开发岗位学习调研

> 目标：面向“大模型应用开发 / Agent 应用开发”岗位，形成能够独立开发、评测、部署和维护 AI 应用的能力与作品集。

## 结论：先成为能交付 AI 产品的后端工程师

不要把学习重心放在“会多少框架名”上。岗位竞争力主要来自以下四点：

1. 能直接使用模型 API，并理解工具调用的执行闭环；
2. 能构建、评测和优化 RAG；
3. 能让 Agent 在可控、可审计的工作流中调用外部系统；
4. 能以 API、数据库、容器、监控和权限控制的方式上线应用。

建议以 **Python + FastAPI + PostgreSQL/pgvector + Docker** 作为主技术栈；前端掌握基础 React / Next.js 即可。还应至少熟悉一家国内模型平台的 API 与 OpenAI 风格 API 的兼容接入方式。

## 技术学习清单与优先级

### 1. Python 与后端工程基础（必学）

- Python：虚拟环境与 `uv`、类型标注、异常处理、日志、配置管理；
- `Pydantic`：请求/响应与工具参数校验；
- `async/await`、`httpx`、并发与重试；
- FastAPI：REST API、依赖注入、文件上传、鉴权、OpenAPI；
- 测试：`pytest`、接口测试、mock；
- 数据库：SQL、PostgreSQL、ORM（SQLAlchemy）；Redis 的缓存、会话或队列用途。

AI 聊天产品应会流式返回。FastAPI 已支持 Server-Sent Events（SSE），适用于向浏览器持续推送文本、工具进度和日志事件：

- [FastAPI SSE 文档](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

### 2. 模型 API 与工具调用（必学）

至少应直接完成一次不依赖 LangChain 的实现，理解：

- system prompt、消息历史、上下文截断；
- 流式输出、结构化输出（JSON Schema）；
- token、延迟与成本控制；
- 限流、超时、指数退避重试与错误处理；
- 多模型路由及模型能力差异。

**Function calling / tool calling** 是核心能力。它不是“模型真的调用了函数”，而是：模型根据定义好的 JSON Schema 产生工具调用请求 → 服务端校验参数与权限 → 服务端执行函数/API → 将结果作为 tool output 回传模型 → 模型生成最终回复。所有会产生副作用的工具都需要权限、审计及人工确认。

- [OpenAI Responses API：工具与自定义函数](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)

### 3. RAG（必学）

RAG 不应止步于“上传 PDF 后切块、向量检索”。完整链路包括：

1. 文档解析：PDF、网页、表格、OCR、元数据清洗；
2. 索引：合理切块、embedding、版本与增量更新；
3. 检索：向量检索、关键词（BM25）、混合检索、过滤；
4. 排序：rerank、多路召回、query rewrite；
5. 生成：上下文拼接、引用溯源、拒答策略；
6. 评测：检索命中、答案忠实性、正确性、延迟与成本。

存储方案建议先用 PostgreSQL + pgvector，掌握后再了解 Qdrant 或 Milvus 的适用场景。

### 4. Agent 与工作流（必学）

- Tool use：工具描述、参数 schema、错误恢复；
- 状态与记忆：短期会话、持久状态、上下文压缩；
- 路由、计划、确定性步骤与非确定性步骤的边界；
- Human-in-the-loop：邮件发送、写库、调用付费接口等操作的审批；
- 任务超时、重试、幂等性、可恢复执行；
- 多 Agent：在单 Agent 与确定性工作流稳定之后再学习。

框架定位：**LangChain 适合组件整合，LangGraph 适合显式状态、分支和可恢复的 Agent 工作流。** 重要的是能解释工作流为何这样设计，而不是只会调用 `create_agent()`。

### 5. MCP（优先学习）

Model Context Protocol（MCP）是连接 AI 应用与外部工具、资源、提示词的开放协议。它不是 Agent 框架，也不取代 function calling；它解决的是让不同客户端以统一方式发现和接入外部能力的问题。

建议完成一个 MCP server，例如只读查询内部知识库、病患随访统计数据或 GitHub 项目的工具。重点掌握工具最小权限、OAuth/密钥、输入校验、审计记录和确认机制。

- [MCP 官方介绍](https://modelcontextprotocol.io/docs/getting-started/intro)
- [MCP 架构规范](https://modelcontextprotocol.io/specification/2025-06-18/architecture)

### 6. 工程化、部署与可观测性（必学）

- Docker、Docker Compose、镜像构建、环境变量和健康检查；
- Nginx / 反向代理、HTTPS、基础云部署；
- JWT / RBAC、密钥管理、文件安全、数据脱敏；
- 日志、trace、请求延迟、token/成本、检索结果与工具调用记录；
- GitHub Actions 等基础 CI/CD。

Kubernetes 可以了解，不建议作为入门阶段的重点。LLM 应用的可观测性尤其重要：应能追踪每次请求的 prompt、模型响应、token、检索与工具调用，从而定位错误和成本问题。

- [Langfuse Observability](https://github.com/langfuse/langfuse-docs/blob/main/content/docs/observability/overview.mdx)

## 推荐学习路径

```text
Python + FastAPI
  → 直接调用模型 API + function calling
  → 基础 RAG
  → PostgreSQL/pgvector + 混合检索/rerank
  → LangChain / LangGraph
  → MCP + 人工审批
  → Docker 部署 + 评测 + 可观测性
```

建议用 6–8 周完成一个可展示项目，而不是同时学习所有框架：

| 阶段 | 建议内容 |
| --- | --- |
| 第 1 周 | Python/FastAPI、直接调用模型、SSE 流式聊天 |
| 第 2–3 周 | PDF/网页解析、pgvector、基础 RAG、引用展示 |
| 第 4 周 | 混合检索、rerank、构建问题集并评测 |
| 第 5 周 | 工具调用、LangGraph 工作流、人工审批 |
| 第 6 周 | Docker Compose、登录权限、日志/Trace、README 与演示视频 |
| 第 7–8 周（可选） | MCP server、多 Agent 或任务队列 |

## GitHub 教程仓库

### 主线推荐

1. [langchain-ai/learning-langchain](https://github.com/langchain-ai/learning-langchain)

   最适合作为从零到一的主线仓库。内容按章节覆盖 LLM 基础、文档处理、RAG、记忆、聊天机器人、Agent、子图、生产化、部署与评测；同时提供 Python 与 JavaScript 示例，也包含 pgvector 的 Docker 环境。

2. [langchain-ai/rag-from-scratch](https://github.com/langchain-ai/rag-from-scratch)

   用于补足 RAG 的原理和基础实现，重点理解索引、检索、生成三阶段，避免只会调用封装。

3. [langchain-ai/langgraph-101](https://github.com/langchain-ai/langgraph-101)

   用于进入 Agent 开发。包含工具、记忆、流式输出、人工审批、多 Agent、生产工作流和本地 Studio 调试。

4. [openai/openai-agents-python](https://github.com/openai/openai-agents-python)

   用于学习 Agent SDK 的工具、guardrails、handoff、MCP、sandbox 和 tracing 示例；尤其适合对照理解 Agent 的底层运行机制。

## 推荐作品集项目

不要只做普通“PDF 问答机器人”。建议做一个 **企业知识库 + 业务工具 Agent**：

- 上传 PDF/网页，异步解析并建立索引；
- 回答附带可点击引用和原文片段；
- 混合检索 + rerank，并给出优化前后的评测对比；
- Agent 可调用自建的订单/CRM/mock 数据库工具；
- 会改变数据或对外发送消息的工具必须等待用户审批；
- FastAPI SSE 流式接口，基础 React/Next.js 前端；
- PostgreSQL + pgvector + Redis + Docker Compose；
- 接入 Langfuse 或同类工具，记录检索、工具调用、耗时与成本；
- README 提供架构图、启动命令、测试集、评测结果与 demo 视频。

## 面试中应能回答的问题

- RAG 为什么检索错？如何从切块、召回、过滤、rerank 和 query rewrite 分层排查？
- 如何评估“回答看似流畅但没有依据”的问题？
- 为什么某个业务流程要用确定性工作流，而不应交给 Agent 自由规划？
- 工具调用如何做权限控制、参数验证、审计、重试和人工审批？
- 如何降低模型调用成本、延迟和失败率？
- 如何部署、监控和复现线上一次错误回答？

真正能拉开差距的不是“会 LangChain”，而是能把以上问题落实为可运行、可评测、可部署、可维护的工程实现。
