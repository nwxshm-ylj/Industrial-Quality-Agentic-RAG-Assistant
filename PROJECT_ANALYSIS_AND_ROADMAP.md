# 工业 Agentic RAG 项目问题分析与演进路线

## 1. 结论

当前项目已经打通文档 RAG、规则查询、历史案例、SQL 分析、LangGraph 路由、FastAPI 和 Streamlit，作为技术原型是完整的。

但它还不具备直接进入真实生产环境的条件。主要短板不在“Agent 节点不够多”，而在以下基础能力：

1. 模型和检索器生命周期不合理，影响启动、内存和并发；
2. 检索、融合、重排分数混用，证据阈值缺少统计依据；
3. SQL 校验、访问控制和敏感数据保护不足；
4. 文档入库和数据库初始化是破坏式操作，缺少版本与回滚；
5. 评估样本少且与演示数据同源，100% 通过率不能代表真实质量；
6. 缺少自动测试、可观测性、超时、降级和发布门禁。

正确的下一步不是继续增加工具，而是按“稳定安全 → 检索提质 → Agent 治理 → 生产试点”的顺序演进。

最终目标应是一个可在单工厂或单业务域生产试点的“证据型工业质量助手”：关键结论有来源，证据不足会拒答，工具权限可控，数据更新可回滚，质量可以持续评估。

---

## 2. 当前能力与成熟度

### 2.1 已具备能力

- FastAPI 提供基础 RAG 和 Agentic RAG 接口；
- Streamlit 展示答案、引用、上下文、工具结果和评估报告；
- LangGraph 根据意图路由到文档、规则、SQL、案例或通用回答；
- Qdrant 向量检索与本地 BM25 融合；
- 可选 CrossEncoder Reranker；
- 支持 FMEA、SOP、规则类 Markdown 入库；
- 规则工具支持 PR 配置与故障关键词；
- PostgreSQL 支持检测记录、设备报警和历史案例；
- SQL Tool 有模板优先、SELECT 限制、表白名单和 LIMIT；
- 证据不足时可以改写查询并重试一次；
- 内置 11 条评估问题和报告脚本。

### 2.2 成熟度判断

| 维度 | 当前水平 | 判断 |
|---|---|---|
| 功能完整度 | 中 | 演示链路完整 |
| 检索质量 | 中低 | 有混合检索，但融合与阈值未校准 |
| 数据工程 | 低 | 仅顶层 Markdown，全量重建 |
| Agent 可靠性 | 中低 | 有路由和兜底，缺少结构化规划 |
| 工具安全 | 低 | SQL 主要依赖提示词和正则 |
| 服务稳定性 | 低 | 生命周期、超时、就绪检查不足 |
| 测试评估 | 低 | 主要是打印脚本，样本过少 |
| 可观测性 | 低 | 依赖 print，无完整 trace 和指标 |
| 安全权限 | 低 | 无认证、授权、审计和数据域隔离 |
| 部署复现性 | 低 | 依赖和部分镜像未锁版本 |

结论：适合内部演示，不适合直接承载真实生产决策。

---

## 3. 问题清单

### 3.1 P0：接入真实数据前必须解决

| 编号 | 问题 | 当前证据 | 风险 | 处理方向 |
|---|---|---|---|---|
| P0-01 | SQL 安全边界不足 | sql_tool.py 用 startswith、正则关键字、表白名单校验 | 高成本函数、长查询或注入导致风险 | AST 校验、只读账号、超时、审计 |
| P0-02 | 无认证和授权 | API 可直接访问并返回 contexts、SQL 行和案例 | 工业数据泄露 | OIDC/API Key、RBAC、ACL、脱敏 |
| P0-03 | 初始化具有破坏性 | init_sql_data.py 执行 DROP TABLE；入库重建 collection | 误删业务数据和索引 | Alembic、独立 seed、影子索引 |
| P0-04 | 资源生命周期不合理 | /chat 每请求创建 Chain；多个节点 import 时创建模型和工具 | 重复加载、内存膨胀、难以测试降级 | lifespan、依赖注入、单实例服务 |
| P0-05 | 内部错误直接暴露 | routes_chat.py 返回 str(e) | 泄露连接、路径和内部实现 | 统一错误码与异常映射 |
| P0-06 | 健康检查无实际意义 | /health 固定返回 ok | 依赖故障时仍被判定健康 | live/readiness 分离 |
| P0-07 | 日志可能泄密 | 多处 print 问题、SQL、上下文、模型响应 | 敏感数据进入日志 | 结构化日志和字段过滤 |
| P0-08 | 依赖不可复现 | requirements 未锁版本，Qdrant 使用 latest | 构建和接口随升级变化 | lockfile、固定镜像、CI 构建 |

### 3.2 P1：直接影响答案质量

1. hybrid_retriever.py 分别对向量和 BM25 做查询内 min-max，再按 0.65/0.35 加权。该分数只反映本次候选相对次序，不能跨问题比较。
2. 只有一个弱相关结果时，min-max 会把它归一化为 1，可能被误判为强证据。
3. BM25-only 的最高加权分通常不超过 0.35，而 evidence_judge 的阈值是 0.55，强关键词命中仍可能被判不足。
4. 启用 Reranker 后将 rerank_score 直接作为 score，但 CrossEncoder 与 hybrid 分数不在同一空间，继续使用 0.55 没有依据。
5. 第二次改写检索会覆盖第一轮 contexts，没有合并与去重，可能丢失第一轮有效证据。
6. 引用只作为独立列表返回，答案正文没有引用编号，结论与证据不能一一对应。
7. 生成主要靠 Prompt 要求“不编造”，没有生成后的事实一致性或引用覆盖检查。
8. Intent 通过自由文本和字符串包含关系解析，复合问题、多意图和否定表达容易误路由。
9. SQL 和案例实体提取依赖有限关键词，难以处理别名、组合条件和复杂时间范围。

### 3.3 P2：影响扩展与维护

- loader.py 只扫描 data/raw_docs 第一层 Markdown；
- requirements 中虽然包含 PDF、DOCX 依赖，但没有实际解析流程；
- doc_type 只根据文件名推断；
- chunk 固定为 500/80，没有按标题、表格、规则结构切分；
- point id 使用顺序编号，无稳定文档 ID 和版本；
- 每次入库删除整个 collection，无法增量更新或回滚；
- BM25 中文只使用单字和 bigram，没有工业词典；
- scripts/test_*.py 主要打印结果，没有断言；
- 11 条评估数据与演示文档高度同源；
- 评估没有 Recall@K、MRR、忠实度、引用准确率和安全指标；
- 初始化随机数据没有固定种子；
- Prompt、阈值和模型配置分散在多个模块；
- FastAPI 使用同步阻塞路径，无流式输出和并发治理；
- API 与 UI 共用偏重镜像，并以 root 运行。

---

## 4. 关键问题的实现判断

### 4.1 生命周期

应使用 FastAPI lifespan 在启动时初始化配置、Qdrant、数据库、Embedding、BM25、Reranker 和 LLM Client，并通过依赖注入提供给 Service 和 Graph Node。

禁止在模块 import 时连接外部系统或加载大模型。这样才能：

- 避免 /chat 每次请求重新加载模型；
- 控制多 worker 内存；
- 注入 fake 组件进行测试；
- 为每个依赖提供 readiness 状态；
- 在关闭时释放资源；
- 对单个组件设置降级策略。

### 4.2 检索与证据

排序分数和证据可信度必须分开。

排序层建议：

1. 原始问题和改写问题分别召回；
2. Dense 与 Sparse 使用 RRF 融合，避免直接混合不同分数空间；
3. Top N 使用统一版本的 CrossEncoder 重排；
4. 保留 dense_score、sparse_score、rrf_score、rerank_score，不能都写入 score；
5. 两轮检索按稳定 chunk_id 合并去重。

证据层建议：

- 单独建立 Evidence Grader；
- 输入问题、候选文本、元数据和引用；
- 输出 supported、confidence、missing_information、reason；
- 阈值由标注集校准；
- 证据不足时返回 insufficient_evidence，不强行生成完整答案。

推荐检索结果字段：

~~~json
{
  "chunk_id": "doc-v2-section-03-01",
  "dense_score": 0.72,
  "sparse_score": 8.35,
  "rrf_score": 0.031,
  "rerank_score": 0.84,
  "rank": 1,
  "evidence_supported": true
}
~~~

### 4.3 Agent 路由

真实问题经常是组合任务，例如：

- 查询最近一周 ZP8 误识别数量，并结合 FMEA 给出原因；
- 查询 PR001 规则，再查历史类似案例；
- 分析报警趋势并给出 SOP 建议。

路由最终应使用结构化输出，而不是单个自由文本标签：

~~~json
{
  "primary_intent": "sql_analysis",
  "secondary_intents": ["fault_diagnosis"],
  "entities": {
    "station": "ZP8",
    "time_range": "7d",
    "defect_type": "wheel_misrecognition"
  },
  "required_tools": ["sql", "rag"],
  "answer_format": "analysis_with_actions"
}
~~~

实现要求：

- 用 Pydantic/JSON Schema 约束输出；
- 保留高频确定性规则作为兜底；
- 只并行执行互不依赖的工具；
- 每个工具设置 timeout、重试和错误类型；
- 设置最大步骤、总 token 和总执行时间；
- 工具失败时返回部分结果和明确缺失信息。

### 4.4 SQL 安全

正则不是安全边界。生产实现至少需要：

1. 数据库账号只授予指定 schema 的 SELECT；
2. 每次查询启用只读事务和 statement_timeout；
3. 用 SQL AST 校验语句、表、列、函数、子查询和 LIMIT；
4. 拒绝危险函数、系统表、全表大扫描和笛卡尔积；
5. 记录用户、问题、生成 SQL、耗时、行数和拒绝原因；
6. 对结果字段做权限过滤和脱敏。

更推荐 LLM 先生成结构化 Query Plan，再由代码生成 SQL：

~~~json
{
  "dataset": "equipment_alarm",
  "metrics": [{"function": "count", "alias": "alarm_count"}],
  "dimensions": ["station"],
  "filters": [
    {"field": "created_at", "operator": "gte_relative_days", "value": 30}
  ],
  "order_by": [{"field": "alarm_count", "direction": "desc"}],
  "limit": 10
}
~~~

只有 Query Plan 无法覆盖的复杂查询才进入严格 AST 校验的 Text-to-SQL 路径。

### 4.5 知识入库

目标入库流程：

~~~text
文档接入
  -> 文件类型、大小和安全检查
  -> 解析与文本规范化
  -> 文档 ID 与版本
  -> 按结构分块
  -> 元数据与 ACL
  -> Embedding
  -> 写入影子 collection
  -> 抽样检索验证
  -> Qdrant alias 原子切换
  -> 保留上一版用于回滚
~~~

每个 chunk 至少需要：

- document_id、document_version、chunk_id；
- source、title、section_path、page_number；
- doc_type、equipment_type、station、product_line；
- effective_date、expiry_date、owner_department；
- confidentiality、acl_tags；
- content_hash、embedding_model_version；
- text。

稳定 point id 应由文档 ID、版本、章节和 chunk 序号生成，而不是简单从 0 开始。

### 4.6 评估

当前仓库的 100% 报告不能作为上线依据，因为样本少、问法简单并与演示数据同源。

必须分层评估：

| 层级 | 指标 |
|---|---|
| 路由 | Intent Accuracy、实体抽取 F1、多意图召回率 |
| 检索 | Recall@K、MRR、nDCG、无答案识别准确率 |
| 重排 | Pairwise Accuracy、nDCG@K |
| 生成 | Faithfulness、Answer Relevance、关键事实准确率 |
| 引用 | Citation Precision、Citation Coverage、可追溯率 |
| SQL | 执行正确率、结果正确率、危险 SQL 拒绝率 |
| 系统 | 成功率、P50/P95、首 token 延迟、单请求成本 |
| 安全 | 越权阻断率、提示注入抵抗、敏感信息泄露率 |

建议建立至少 200 条业务专家标注的数据，划分开发集、回归集和盲测集。每份报告必须记录代码、数据、模型、Prompt 和参数版本。

---

## 5. 最终目标

### 5.1 产品目标

形成可在单工厂或单业务域生产试点的工业质量知识与诊断助手：

- 对 FMEA、SOP、质量标准、设备手册和规则进行可追溯问答；
- 联合历史案例、规则和结构化数据给出诊断建议；
- 区分事实、推断、缺失信息和建议；
- 关键结论定位到具体文档版本、页码、规则或 SQL 结果；
- 对无证据、越权和高风险请求拒答或转人工；
- 支持知识更新、版本回滚、权限、审计和持续评估；
- 在可控延迟和成本下稳定运行。

### 5.2 明确非目标

系统不应默认：

- 自动修改 MES、PLC、设备参数或质量规则；
- 自动放行产品或替代质量签字；
- 在没有证据时给出确定性根因；
- 执行任意 LLM 生成 SQL；
- 跨部门、产线或租户访问未授权数据。

系统定位是“有证据的决策辅助”，不是无人监督的生产控制。

### 5.3 试点指标

以下目标需要用真实业务数据校准：

| 指标 | 目标 |
|---|---|
| 意图识别准确率 | 大于等于 95% |
| 实体抽取 F1 | 大于等于 90% |
| 文档检索 Recall@5 | 大于等于 90% |
| 引用准确率 | 大于等于 95% |
| 回答忠实度 | 大于等于 90% |
| 无答案正确拒答率 | 大于等于 90% |
| SQL 结果正确率 | 大于等于 95% |
| 危险或越权 SQL 阻断率 | 100% |
| API 成功率 | 大于等于 99.5% |
| Warm 检索 P95 | 小于 1 秒 |
| 端到端 P95 | 小于 12 秒，按模型校准 |
| 严重数据泄露事件 | 0 |

---

## 6. 目标架构

~~~text
Web / API / 企业应用
          |
认证、RBAC、限流、审计上下文
          |
Orchestrator API
LangGraph + 步骤、时间、Token 预算
          |
结构化 Router + Policy Engine
          |
  +-------+-----------+-------------+----------------+
  |                   |             |                |
Document RAG      Rule Service  Case Service   Analytics Service
  |                                            Query Plan
Dense + Sparse                                  SQL AST
  |                                                |
RRF -> Rerank                              Read-only PostgreSQL
  |
Evidence Grader
  |
Grounded Generator
  |
Citation Verifier
  |
统一响应、Trace、Metrics、Feedback

知识侧：
Document Store
 -> Parse
 -> Version
 -> Chunk + Metadata + ACL
 -> Embed
 -> Versioned Qdrant Collection
 -> Validate
 -> Alias Switch

质量侧：
Golden Dataset
 -> Offline Evaluation
 -> Regression Gate
 -> Canary Release
 -> Online Feedback
~~~

---

## 7. 分阶段实现路径

工期按 1 至 2 名熟悉 Python、RAG 和后端工程的人员估算。

### 阶段 0：可信基线，第 1 周

目标：后续优化可以被客观比较。

任务：

- 固定模型、Prompt、依赖和数据版本；
- 固定样例数据随机种子；
- 保存可复现 baseline；
- 把打印脚本迁移为 pytest 断言；
- 增加静态检查、单元测试和 API smoke test；
- 记录启动时间、内存、P50/P95 和调用成本；
- 将评估集扩充到至少 50 条，加入无答案和错误路由。

交付：

- 依赖锁文件；
- tests/unit、tests/integration、tests/e2e；
- baseline_eval.json；
- CI 配置。

验收：

- 同环境连续两次结果可复现；
- 核心工具有断言；
- 测试失败时禁止合并。

### 阶段 1：稳定性与安全底座，第 2 至 3 周

任务：

- 用 lifespan 和依赖注入重构模型、Retriever、LLM 和工具；
- /chat 与 /graph-chat 复用实例；
- 新增 /health/live 和 /health/ready；
- LLM、Qdrant、数据库设置连接、读取和总超时；
- 建立统一异常、错误码和安全响应；
- 用结构化 logging 替换 print；
- 引入 Alembic，拆分 migrate 和 seed；
- 使用 PostgreSQL 只读应用账号；
- 设置 statement_timeout 和只读事务；
- Docker 加 healthcheck、固定镜像版本、非 root 用户；
- 增加 API Key 或企业 OIDC 与角色校验。

建议新增：

- app/core/lifespan.py；
- app/core/dependencies.py；
- app/core/errors.py；
- app/core/logging.py；
- app/services/rag_service.py；
- migrations/。

验收：

- 连续 100 次请求不重复加载模型；
- 依赖不可用时 readiness 失败；
- 对外错误不包含连接串、内部路径或堆栈；
- 应用账号无法执行 DML 和 DDL；
- 认证与越权测试通过。

### 阶段 2：知识与检索质量，第 4 至 6 周

任务：

- 定义 Document、DocumentVersion、Chunk 模型；
- 支持 Markdown、PDF、DOCX 并保留标题和页码；
- 增加 hash、版本、增量更新和删除；
- 使用影子 collection + alias 发布与回滚；
- 使用稳定 point id；
- 建立工业术语词典和更可靠的中文分词；
- 用 RRF 替代未校准的 min-max；
- 对 Top N 重排；
- 分离各阶段分数字段；
- 用评估集选择 top_k、chunk、overlap、rerank_k；
- 实现 Evidence Grader；
- 合并去重多轮检索；
- 输出文档版本、页码和段落引用。

建议新增：

- app/ingestion/loaders.py；
- app/ingestion/pipeline.py；
- app/ingestion/index_manager.py；
- app/retrieval/dense.py；
- app/retrieval/sparse.py；
- app/retrieval/fusion.py；
- app/retrieval/evidence.py。

验收：

- Recall@5 达标；
- 无关问题不会被归一化为高证据；
- Reranker 开关不复用错误阈值；
- 更新单个文档不删除整个索引；
- 引用可以定位文件版本和页码/章节。

### 阶段 3：Agent 与工具治理，第 7 至 8 周

任务：

- Router 改为结构化输出；
- 抽取工位、设备、PR、缺陷、时间范围；
- 支持主意图和次意图；
- 建立统一 ToolResult 协议；
- SQL 优先 Query Plan 编译；
- Text-to-SQL 使用 AST 校验；
- 案例升级为结构化过滤 + 文本/向量召回；
- 规则增加 schema、生效日期和版本；
- 工具加入 timeout、重试、熔断和降级；
- 限制 Agent 最大步骤、Token 和时间；
- 生成后验证引用覆盖和事实一致性。

验收：

- 组合问题可以正确调用多个受控工具；
- 工具失败时返回部分结果和缺失项；
- SQL 安全集全部正确允许或拒绝；
- Agent 不会无限循环；
- 关键结论都有引用。

### 阶段 4：生产试点，第 9 至 12 周

任务：

- 企业 SSO、RBAC、文档 ACL 和数据域；
- 操作审计和 SQL 审计；
- 异步或流式响应；
- 并发限制、队列和背压；
- 安全缓存；
- OpenTelemetry 或等价 Trace；
- 成功率、延迟、错误、Token、成本仪表盘；
- Qdrant、PostgreSQL 和 LLM 告警；
- 压测、故障注入和恢复演练；
- 开发、测试、预生产和生产环境隔离；
- Canary 发布和评估门禁；
- 用户反馈和业务专家复核闭环；
- 数据分级、脱敏、保留和删除机制。

验收：

- 达到试点指标；
- 通过安全与数据合规评审；
- 依赖故障有明确降级；
- 有发布、回滚和值班手册；
- 业务专家盲测验收。

---

## 8. 推荐代码结构

~~~text
app/
├── api/
│   ├── routes_chat.py
│   ├── routes_health.py
│   └── dependencies.py
├── core/
│   ├── config.py
│   ├── lifespan.py
│   ├── errors.py
│   ├── logging.py
│   ├── security.py
│   └── telemetry.py
├── domain/
│   ├── documents.py
│   ├── retrieval.py
│   ├── tools.py
│   └── chat.py
├── services/
│   ├── rag_service.py
│   └── orchestration_service.py
├── ingestion/
│   ├── loaders.py
│   ├── chunker.py
│   ├── pipeline.py
│   └── index_manager.py
├── retrieval/
│   ├── dense.py
│   ├── sparse.py
│   ├── fusion.py
│   ├── reranker.py
│   └── evidence.py
├── tools/
│   ├── rules/
│   ├── cases/
│   └── sql/
│       ├── planner.py
│       ├── validator.py
│       └── executor.py
├── prompts/
└── repositories/

tests/
├── unit/
├── integration/
├── e2e/
├── security/
└── eval/

migrations/
docs/
~~~

不要一次性大规模重写。应在对应阶段沿清晰边界逐步迁移。

---

## 9. 关键协议

### 9.1 统一工具结果

~~~json
{
  "tool": "sql",
  "status": "success",
  "data": {},
  "citations": [],
  "latency_ms": 238,
  "error_code": null,
  "retryable": false
}
~~~

### 9.2 最终响应

~~~json
{
  "request_id": "req_xxx",
  "answer": "结论正文，并包含 [1][2] 引用标记",
  "answer_status": "grounded",
  "intent": {},
  "citations": [
    {
      "id": 1,
      "source_type": "document",
      "document_id": "doc_xxx",
      "version": "2026-06-01",
      "page": 12,
      "section": "故障排查",
      "chunk_id": "chunk_xxx"
    }
  ],
  "missing_information": [],
  "warnings": [],
  "trace_summary": {
    "tools": ["rag"],
    "latency_ms": 2840
  }
}
~~~

answer_status 至少包含：

- grounded：证据充分；
- partial：部分问题有证据；
- insufficient_evidence：证据不足；
- rejected：权限或安全拒绝；
- failed：系统错误。

---

## 10. 两周内立即执行的任务

### 第一周

- [ ] 固定 Python 依赖和容器版本；
- [ ] 显式声明 langchain-text-splitters 等直接依赖；
- [ ] 固定样例数据随机种子；
- [ ] 将 Rule Tool 和 SQL Validator 迁移为 pytest；
- [ ] 为三个 API 增加 smoke test；
- [ ] 禁止向客户端返回 str(e)；
- [ ] 用 logging 替换 print 并过滤敏感字段；
- [ ] 增加 live 和 ready；
- [ ] 为 Compose 服务增加 healthcheck；
- [ ] 建立第一版 CI。

### 第二周

- [ ] 用 lifespan 初始化并复用模型与客户端；
- [ ] 删除节点模块中的外部资源全局实例；
- [ ] 让 /chat 不再按请求加载模型；
- [ ] 引入 Alembic；
- [ ] 拆分 migrate 和 seed；
- [ ] 建立数据库只读账号；
- [ ] 设置 statement_timeout 和只读事务；
- [ ] 增加 SQL 安全集；
- [ ] 评估集扩展到 50 条；
- [ ] 保存可复现 baseline。

两周结束时，功能不会明显增加，但项目会从“容易演示”提升为“可以可靠迭代”。

---

## 11. 实施原则

1. 确定性优先：规则、模板查询、权限由代码完成；
2. LLM 最小授权：负责理解、规划和表达，不直接拥有无限执行权；
3. 证据优先：没有证据时明确说明；
4. 分数不混用：每个检索阶段保留独立语义；
5. 数据可版本化：文档、索引、规则、Prompt、模型、评估可追踪；
6. 默认最小权限：数据库、文档和工具从最小权限开始；
7. 失败可解释：错误有阶段、错误码和重试策略；
8. 优化必须评估：无指标支撑的改动不直接发布；
9. 避免过早多 Agent：先把单图编排做好；
10. 业务专家参与：工业诊断不能只由开发或自动指标判定。

---

## 12. 主要风险

| 风险 | 缓解措施 |
|---|---|
| 真实问法与演示集差异大 | 尽早收集脱敏真实问题和失败案例 |
| 同一术语跨产线含义不同 | 元数据增加工厂、产线、设备、车型范围 |
| 检索到过期 SOP | 增加生效日期、失效日期和版本优先级 |
| LLM 服务波动 | 超时、重试、熔断、结构化校验、备用模型 |
| 模型升级产生回归 | 固定版本、盲测、门禁、Canary |
| SQL 口径被误读 | 返回过滤条件、SQL、口径和数据时间 |
| 跨域权限泄露 | 检索前 ACL 过滤，禁止检索后过滤 |
| 多工具导致成本增长 | 步骤预算、Token 预算、缓存、成本监控 |

---

## 13. 生产试点完成定义

只有满足以下条件，项目才能从原型进入生产试点：

- 依赖固定且环境可重复构建；
- 数据迁移与样例初始化完全分离；
- 文档支持版本、增量更新、回滚和 ACL；
- 检索、重排、证据分数经评估标定；
- 关键结论有可定位引用；
- 无证据问题能可靠拒答；
- SQL 有只读账号、AST/Query Plan、超时和审计；
- API 有认证、授权、限流和敏感信息保护；
- 有结构化日志、Trace、指标和告警；
- 自动测试覆盖单元、集成、端到端、安全和评估；
- 真实业务盲测达到约定指标；
- 有发布、回滚、故障处理和恢复手册；
- 业务负责人确认其决策辅助边界。

---

## 14. 最终建议

项目下一步最重要的不是增加更多模型或 Agent，而是把“能回答”升级为：

- 回答有证据；
- 过程可控制；
- 数据不泄露；
- 结果可评估；
- 故障可恢复；
- 版本可追踪。

推荐投入顺序：

1. 两周完成稳定性、安全和测试底座；
2. 三周完成知识版本化、检索融合和证据校准；
3. 两周完成结构化路由、工具协议和 SQL 强治理；
4. 三至四周完成权限、观测、性能和生产试点；
5. 后续通过真实反馈持续优化，不堆叠未经评估的链路。

最终系统应成为工业质量工程师可信赖的“证据型助手”：知道什么时候查规则、查数据、检索文档，也知道什么时候证据不足并停止推断。
