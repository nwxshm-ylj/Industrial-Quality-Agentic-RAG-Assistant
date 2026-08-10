# 独立检索评估方案

## 1. 目的

独立检索评估只测在线搜索层，把检索回归与意图路由、LangGraph、答案生成和记忆系统分离。这样可以判断问题来自“没有召回正确资料”，还是“召回正确但生成回答不佳”。

当前被评估链路：

```text
question
→ 本地 BGE-M3 query embedding
→ Qdrant industrial_docs_active
→ OpenSearch BM25
→ RRF 或 Weighted Fusion
→ 可选 Reranker
→ ranked contexts
```

评估器不读取 `chunks.json`，也不调用答案生成 LLM。默认本地 BGE-M3 不产生 API 费用；启用在线 Embedding Provider 时需要单独评估调用成本。

## 2. 数据集

默认文件：`data/eval/retrieval_eval_questions.json`

```json
{
  "id": "RET001",
  "question": "轮毂识别异常可能是什么原因？",
  "relevance_field": "source",
  "relevant_ids": ["ai_vision_fmea.md"]
}
```

支持按 `source`、`doc_id`、`chunk_id` 标注。生产评估优先使用稳定 doc_id/chunk_id，并由领域专家审核相关性标签。

同一文档多个 Chunk 会按 relevance_field 去重，避免一个相关文档重复命中导致文档级指标虚高。

## 3. 指标

- `Precision@K`：Top K 中相关唯一结果占 K 的比例；
- `Recall@K`：Top K 找到的相关唯一结果占全部标注相关结果的比例；
- `HitRate@K`：至少命中一个相关结果的问题比例；
- `MRR@K`：第一个相关结果排名倒数的平均值；
- `nDCG@K`：考虑排名位置的归一化折损累计增益；
- 延迟：min、avg、P50、P95、P99、max；
- 组件延迟：Qdrant、OpenSearch、Fusion、Reranker；
- Degraded Rate：从 Hybrid 降级为 vector-only 的问题比例。

失败问题不会被静默跳过，而是以零分计入分母；运行状态为 completed、partial 或 failed。

## 4. 命令

完全离线的 Mock 测试：

```powershell
python -m scripts.test_retrieval_evaluation
python -m scripts.test_metrics
python -m scripts.test_online_hybrid_retriever
python -m scripts.test_rrf_fusion
python -m scripts.test_weighted_fusion
```

真实在线索引评估：

```powershell
docker compose exec api python -m scripts.evaluate_retrieval --top-k 5 --k-values 1,3,5
```

只评估 BGE-M3 + Qdrant + OpenSearch + RRF，不加载 Reranker：

```powershell
docker compose exec -e USE_RERANKER=false api python -m scripts.evaluate_retrieval
```

输出：

- 最新报告：`data/eval/retrieval_eval_report.json`；
- 版本化报告：`data/eval/retrieval_eval_report_<run_id>.json`。

## 5. API

- `POST /api/v1/evaluation/retrieval/run`；
- `GET /api/v1/evaluation/retrieval/runs`；
- `GET /api/v1/evaluation/retrieval/runs/{run_id}`。

仅 admin/engineer 可运行和查看。

## 6. 结果解释

不能只看一个 Recall@5：

1. Recall 高、MRR 低：相关资料找到了，但排序靠后；
2. Precision 低、Recall 高：召回面广但噪声多，可能需要 Reranker 或过滤；
3. 向量好、关键词差：检查分词、字段 mapping、业务代码和同义词；
4. 关键词好、向量差：检查 query rewrite、Embedding 模型、维度、Alias 和索引版本；
5. 冷启动慢、热请求快：区分模型加载时间与稳定运行延迟；
6. 指标高但数据集很小：只能说明样例回归通过，不能代表生产准确率。

## 7. 版本化要求

每份评估报告至少应关联：

- 数据集版本；
- parser_version 和 chunk_strategy；
- Embedding provider/model/dimension/index_version；
- Qdrant Collection/Alias 目标；
- OpenSearch index version；
- fusion strategy、rrf_k 或权重；
- Reranker 模型与开关；
- top_k 和过滤条件。

只有把数据集、索引和检索参数一起版本化，A/B 对比才有意义。
