# Interview Notes

这份材料用于面试、项目答辩和代码走查。建议先讲业务问题，再讲架构决策，最后主动说明边界和下一步，而不是逐个罗列技术名词。

## 1. 两分钟项目介绍

> 这是一个面向制造质量场景的企业级 Agentic RAG 项目。现场问题并不都是文档问答：有些是故障诊断，有些要查确定性规则，有些要查历史案例，还有些要分析 PostgreSQL 中的检测和报警数据。因此我没有把所有问题都送进同一个向量检索链，而是使用 LangGraph 做显式意图路由。
>
> 文档路径采用 Qdrant 向量检索和 BM25 混合召回，可选 Reranker，并通过 Evidence Judge 判断证据是否充分，不足时进行一次查询改写和重试。规则、SQL、历史案例分别走 Rule Tool、受限 SQL Tool 和 Case Retriever。所有路径最终统一进入答案生成，并把最近对话按 session_id 保存到 PostgreSQL，支持连续追问。
>
> 在企业能力上，项目还实现了 md、txt、pdf、docx 文档上传、版本、增量索引、删除和重建；使用 JWT、admin/engineer/viewer RBAC 和操作审计保护高风险功能；通过 request_id、节点耗时和 JSON 日志提供可观测性；最后把用户反馈、离线评估、指标看板串成质量闭环。整个项目使用 Docker Compose 运行 FastAPI、Streamlit、PostgreSQL 和 Qdrant。

如果时间只有 30 秒，保留四点：

1. 多路 Agentic 工作流，不是单链 RAG。
2. Vector + BM25 + Evidence Judge。
3. 知识库管理 + JWT/RBAC + 审计。
4. request_id + 用户反馈 + 评估闭环。

## 2. 架构讲解顺序

建议按一次请求的生命周期讲：

1. 用户在 Streamlit 登录，API 签发 JWT。
2. graph-chat 中间件生成 request_id。
3. LangGraph 先按 session_id 加载历史消息。
4. Intent Router 选择 Rule、SQL、Case、Document 或 General 路径。
5. 文档路径经过 Query Rewriter、Hybrid Retriever 和 Evidence Judge。
6. 所有路径统一生成答案并保存会话。
7. 响应返回 citations、memory_messages、证据指标和 total latency。
8. 日志与审计记录请求，用户可基于同一个 request_id 提交反馈。
9. EvaluationService 运行版本化问题集并落库指标。

然后补充两个旁路：

- DocumentService 管理 PostgreSQL、Qdrant 和 chunks.json 三份索引/元数据。
- Auth/Audit 位于业务链路外层，不侵入每个节点，但 SQL Tool 保留第二道权限检查。

## 3. 为什么使用 LangGraph

传统顺序链适合固定的 retrieve → generate，但这里存在：

- 多个意图和不同数据源。
- Rule Tool 未命中后回退到文档 RAG。
- Evidence 不足时回到 Query Rewriter 重试。
- 所有路径最终统一生成并保存 memory。
- state 需要携带工具结果、证据、重试次数、用户和 request_id。

LangGraph 的价值是显式状态机：

- 节点职责清晰，可独立测试。
- 条件边可读，避免大量嵌套 if/else。
- 状态字段让引用、工具结果和观测信息可追踪。
- 后续容易增加审批节点、人工确认、超时和持久化 checkpoint。

要主动说明：LangGraph 不是因为“Agent 流行”才使用，而是因为业务确实包含分支、回退和状态。

## 4. 为什么使用 Hybrid Search

只用向量检索的问题：

- PR001、TQ001、VIN、工位名等短代码的语义表示不稳定。
- 工业文档中精确型号和参数通常比语义相似更重要。
- 中文术语、英文缩写和数字混排可能造成向量召回偏差。

只用 BM25 的问题：

- 用户表达与文档术语不一致时召回较差。
- “识别异常怎么处理”和“视觉检测误判排查”可能词面不同但语义接近。
- 多轮补全后的自然语言查询更适合语义检索。

因此：

- Qdrant 负责语义召回。
- BM25 负责精确关键词、编号和术语。
- 融合分数综合两者。
- 可选 Reranker 对候选进行更精细排序。
- Evidence Judge 用评估阈值约束生成入口。

权重 0.65/0.35 是当前默认值，生产中应由评估集和线上反馈驱动，而不是凭经验固定。

## 5. 为什么需要 RBAC

这个系统不仅“读文档”：

- SQL analysis 会访问结构化生产数据。
- 文档删除和重建会改变检索结果。
- 用户管理涉及身份和权限。
- 反馈列表可能包含问题、回答和业务上下文。
- 评估运行消耗模型资源。

角色设计：

- admin：治理和破坏性操作。
- engineer：业务使用、SQL、上传、反馈分析和评估。
- viewer：普通问答、文档查看和反馈提交。

实现上不能只隐藏前端按钮：

- FastAPI Depends 校验 Bearer Token 和 active user。
- require_roles 在路由层做授权。
- SQL Tool 在节点执行前再次检查 role。
- 401 与 403 语义分离。
- permission_denied 写入日志和审计表。

生产扩展方向是多租户、部门/产线范围、文档 ACL 和策略引擎。

## 6. 为什么需要反馈闭环

离线评估不能覆盖所有真实表达和现场长尾问题。没有反馈时只能看“模型是否返回”，无法知道“答案是否有用”。

反馈记录：

- request_id：定位精确运行。
- session_id：关联对话上下文。
- question / answer：保留评审对象。
- rating / comment：用户质量信号。
- intent / citations / metadata：分析路由、来源、证据和延迟。

闭环过程：

~~~text
线上问题与回答
  -> 用户反馈
  -> 按意图/评分分析
  -> 补文档、改 Prompt、调检索或修规则
  -> 离线评估回归
  -> 发布新版本
  -> 继续收集反馈
~~~

要说明局限：用户反馈有偏差，不能直接作为唯一训练标签；需要去重、抽样复核、权限控制和隐私治理。

## 7. 可观测性如何设计

三个关联键：

- request_id：一次 API/Graph 执行。
- session_id：多轮会话。
- username/role：操作主体。

两类记录：

- JSON 运行日志：节点、状态、latency、error。
- PostgreSQL 审计：谁在何时对什么资源执行了什么动作。

响应 metadata 让前端和测试可以直接验证 intent、evidence、retry 和 total latency。审计写入失败不阻断主流程，是为了避免“监控系统故障导致业务不可用”，但必须输出 error log 并设置告警。

## 8. 知识库管理为什么同时写三处

- PostgreSQL 是元数据和 chunk 的事实记录，支持状态、版本、列表和审计。
- Qdrant 是向量在线检索索引。
- chunks.json 兼容现有 BM25 实现。

上传事务跨 PostgreSQL、Qdrant 和文件系统，当前 v1.0 采用状态字段和失败标记控制，而不是分布式事务。失败后可以通过 reindex 修复。

改进方向：

- outbox/event + 异步 worker。
- 可重试、幂等任务状态机。
- 对象存储替代本地文件。
- 统一在线 Hybrid Search，消除 chunks.json 热更新问题。

## 9. 项目难点

### 9.1 多路径输出统一

Rule、SQL、Case 和 Document 的数据格式不同。解决方式是统一映射为 contexts、citations 和 tool_result，再由 Generator 输出。

### 9.2 多轮指代不能污染事实依据

Memory 只用于理解指代和改写查询，答案仍要求以当前检索 evidence 为主要依据。

### 9.3 增量文档不能覆盖旧数据

Qdrant point ID 必须稳定唯一，删除必须按 payload.doc_id 过滤，不能重建整个 collection。legacy ingest 流程继续保留但与增量 API 明确区分。

### 9.4 SQL 安全

SQL Tool 只允许 SELECT、白名单表和 LIMIT，并通过 RBAC 限制角色。生产仍需数据库只读账号、独立 schema、statement timeout 和更严格 SQL parser。

### 9.5 可观测信息跨层传递

request_id 从 FastAPI 中间件进入 graph state，再出现在节点日志、响应、反馈和审计中，使问题可关联而不是只看孤立日志。

### 9.6 测试依赖外部服务

集成测试依赖 PostgreSQL、Qdrant、Embedding 和 LLM。项目通过 Docker Compose 和明确的测试脚本降低环境差异，但后续还需要 mock/unit test 和 CI 中的可控模型桩。

## 10. 项目不足

面试中应主动说明：

- init_sql_data 会重建三张演示业务表，不是正式 migration。
- BM25 文件更新后需要重启 API 才能刷新内存索引。
- 文档入库和评估是同步操作，长任务会占用请求线程。
- 没有多租户和文档级 ACL。
- 没有 OpenTelemetry trace、Prometheus metrics 和集中日志部署。
- 评估指标偏规则化，缺少人工标注和 LLM-as-a-Judge 交叉验证。
- 上传文件缺少病毒扫描、对象存储、配额和内容安全策略。
- SQL 校验是受限实现，不等同于完整 SQL 沙箱。
- 模型、Prompt、索引和数据集尚未统一版本化。
- Docker 镜像和 Python 依赖还需要严格锁定和供应链扫描。

主动说明边界比宣称“生产可直接使用”更可信。

## 11. 后续优化优先级

### P0：安全与可靠性

1. Alembic migration。
2. 只读 SQL 账号、超时、资源限制。
3. 密钥管理、默认密码强制变更。
4. 文件扫描、上传配额、对象存储。
5. 依赖锁定、镜像固定、CI 安全扫描。

### P1：规模化

1. Celery/RQ/Arq 或消息队列处理入库与评估。
2. 多租户和数据范围权限。
3. BM25/稀疏向量在线化。
4. 缓存、连接池和模型服务拆分。
5. 评估任务状态与进度查询。

### P2：质量运营

1. RAGAS 与 LLM-as-a-Judge。
2. Prompt/模型/索引版本。
3. 线上指标趋势和版本对比。
4. 负反馈自动聚类和待办。
5. A/B 测试与灰度发布。

## 12. 常见追问

### 为什么不用一个大模型直接回答？

制造场景要求可追溯和权限边界。规则、SQL 和案例是确定性或结构化数据，直接生成会降低可靠性。

### 为什么不用 Elasticsearch？

当前体量下 Qdrant + 本地 BM25 更轻量，能清楚展示混合检索原理。规模扩大后可考虑 OpenSearch/Elasticsearch 或支持稀疏向量的统一引擎。

### 为什么会返回 contexts？

便于演示、调试和评估。生产环境应按权限裁剪，避免泄露敏感原文。

### 如何证明效果变好？

固定版本的评估集 + 指标趋势 + 真实用户反馈 + 人工抽检。不能只展示一次成功回答。

### 如何避免提示注入？

当前主要依赖参考资料约束。生产需要文档信任分级、Prompt injection 检测、工具参数校验、输出策略和敏感操作人工确认。

### 系统最值得展示的点是什么？

不是某个模型调用，而是从数据治理、Agent 编排、安全、可观测性到反馈评估的完整工程闭环。
