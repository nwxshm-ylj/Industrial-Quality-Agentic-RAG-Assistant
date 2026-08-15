# 系统功能演示脚本

本文提供一套 15～20 分钟的完整演示流程，用于项目评审、功能验收或录制产品演示。演示内容以当前代码功能为准。

## 1. 演示前准备

```powershell
docker compose --profile deepdoc up -d
docker compose --profile tools run --rm init-sql
docker compose ps
curl.exe http://localhost:18000/health/ready
```

访问地址：

- React 管理台：http://localhost:30080
- Streamlit：http://localhost:30000
- Swagger：http://localhost:18000/docs
- Qdrant：http://localhost:6333/dashboard
- Neo4j：http://localhost:7474
- Grafana：http://localhost:3000

准备一个 `demo_quality_sop.txt`：

```text
轮毂识别异常排查 SOP
1. 优先检查相机曝光、镜头污染和安装位置。
2. 确认相机标定状态。
3. 核对车型、轮毂型号和 PR 配置。
4. 检查 MES 配置同步与网络上传状态。
```

## 2. 登录与角色

1. 使用管理员账号登录。
2. 展示当前用户名、角色和退出入口。
3. 说明 Token 保存在前端会话中，所有受保护请求均携带 Authorization Header。

验收点：

- 登录成功；
- 未登录请求返回 401；
- Viewer、Engineer、Admin 的菜单和按钮不同；
- 后端仍会再次执行 RBAC，隐藏按钮不是安全边界。

## 3. 上传工业文档

1. 打开“知识库管理”。
2. 上传 `demo_quality_sop.txt`。
3. doc_type 选择 SOP，version 填写 v1。
4. 等待状态变为 indexed。

讲解链路：文件名清洗与哈希去重 → 解析 → layout-token-v2 切分 → PostgreSQL → Qdrant staging → OpenSearch staging → 双路 promotion → indexed。

验收点：返回 doc_id、chunk_count、parser 和状态；文档列表中可查看版本和更新时间。

## 4. 文档生命周期

1. 查看文档详情和 Chunk 数。
2. 使用同一文件重复上传，展示 content_hash 去重。
3. 管理员执行 reindex。
4. 演示删除指定文档，不影响其他文档。

强调：只有 Qdrant 和 OpenSearch 都成功，文档才能标记为 indexed；失败时保留 failed_stage 和 error_message，可重复 reindex 修复。

## 5. 普通 RAG 问答

提问：

```text
轮毂识别异常可能是什么原因？
```

展示：

- intent 为 rag，query_features.diagnosis_required 为 true；
- Query Rewriter 的独立检索问题；
- Qdrant + OpenSearch 双路命中；
- RRF/Reranker 分数；
- citations 的 source、chunk_id、page_number；
- evidence_score 和 evidence_enough；
- request_id 与 total_latency_ms。

## 6. 多轮记忆

保持同一个 session_id，继续提问：

```text
那优先排查哪个？
```

展示第二轮 `memory_messages` 中包含第一轮问答，并说明历史被用于 Intent Router、Query Rewriter 和 Answer Generator。

如果启用分层记忆，再展示 metadata 中的：

- memory_mode；
- recent_memory_count；
- episodic_memory_count；
- memory_degraded 和 degraded_components。

## 7. 标准与规则知识检索

提问知识库文档中的质量标准、配置要求或判定规则。

验收点：

- intent 为 rag；
- 规则问题与标准文档统一进入 Hybrid Retrieval；
- citation 指向实际上传的标准作业文档；
- Evidence Judge 对规则证据执行与普通知识问答一致的门禁。

## 8. SQL Tool

使用 admin 或 engineer 提问：

```text
最近一周 ZP8 轮毂误识别有多少条？
```

展示模板 SQL、结果行数和审计记录。再切换 viewer，说明 viewer 在 SQL Tool 节点前被拒绝。

安全点：只允许 SELECT、白名单表、禁止危险关键字、LIMIT 自动补齐且最大 100。

## 9. 统一知识检索与案例追溯

提问：

```text
查询与轮毂误识别相关的 LessonLearn、制造标准、风险和处理措施。
```

展示 Qdrant 与 OpenSearch 的统一检索证据，以及 Neo4j 补充的“质量实体—Chunk—文档”关系路径。说明一级 intent 仍为 `rag`，追溯能力由 `query_features.traceability_required` 激活，不再进入独立 Case 节点。

## 10. 流式响应与节点进度

在 React 聊天页面发送问题，展示：

- 当前执行阶段；
- load_memory、intent_router、query_rewriter、retrieve、evidence_judge、generate、save_memory 节点进度；
- answer token 逐步输出；
- 最终 result 与非流式响应字段兼容。

## 11. 提交答案反馈

在回答下选择 positive、neutral 或 negative，填写备注并提交。

验收点：反馈包含 request_id、session_id、question、answer、intent、citations 和 metadata；管理员/工程师可查看统计，viewer 只能提交。

## 12. RAG 评估看板

1. 打开“RAG Evaluation”。
2. 查看正向率、负向率和按意图统计。
3. 运行独立检索评估，展示 Recall、MRR、nDCG 和延迟。
4. 环境具备 Judge 模型时运行 RAGAS，展示 Context Precision、Context Recall、Faithfulness 和 Response Relevancy。

强调：独立检索评估不调用答案生成 LLM；小规模内置数据集只用于回归，不能当作生产准确率。

## 13. 可观测性与审计

1. 复制一次问答的 request_id。
2. 在可观测性页面查询请求详情。
3. 展示节点耗时、LLM 调用、Embedding、检索分阶段延迟和 Token Usage。
4. 打开审计日志，查看登录、graph_chat、SQL、文档上传/重建/删除和权限拒绝。

## 14. 演示收尾

用一条链路总结：

```text
文档解析与双索引
→ 在线 Hybrid Search
→ LangGraph 多意图工具路由
→ Evidence Judge 与引用生成
→ 分层记忆
→ request_id 可观测性
→ 用户反馈和离线评估闭环
```
