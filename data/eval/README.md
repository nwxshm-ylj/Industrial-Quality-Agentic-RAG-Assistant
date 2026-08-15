# 第一版评测问题库（baseline-v1）

本目录中的第一版评测集基于 2026-08-13 已入库且状态为 `indexed` 的 28 份真实文档建立，不使用早期示例文档或虚构标准值。

## 数据集

### `eval_questions.json`

用于端到端 RAG 问答评测：

- 44 个主问题；
- 其中 42 个为可回答问题，2 个为知识缺口拒答问题；
- 其中 4 个问题配置了同一 `session_id` 下的 `followup_question`，共执行 48 次问答交互；
- 覆盖 16 个标准手册问题、20 个 LessonLearn 问题、6 个跨文档追溯问题和 2 个知识缺口问题；
- 覆盖意图、文档类型、来源、答案关键词和多轮记忆检查。

现有 `scripts.evaluate_system` 会直接使用以下字段：

- `id`
- `question`
- `expected_intent`
- `expected_doc_type`
- `expected_source_contains`
- `expected_answer_keywords`
- `followup_question`
- `expected_followup_keywords`

字段 `category`、`answerable` 和 `expected_sources` 同时用于人工复核与 G3.1 生成可信度验收。`answerable=false` 默认要求最终拒答；可回答的 RAG 问题默认要求通过引用契约。需要覆盖默认行为时，可为题目显式增加 `must_cite`、`should_abstain` 和 `forbidden_claims`。

G3.1 在原有意图、来源、关键词和记忆指标之外增加：

- `citation_validation_pass_rate`：需要引用的问题中，最终答案通过引用契约的比例；
- `avg_citation_coverage`：事实要点的平均引用覆盖率；
- `semantic_validation_coverage_rate`：需要引用的问题中，实际完成 Claim-Evidence 语义验证的比例；
- `semantic_support_pass_rate`：需要引用的问题中，最终保留主张全部被引用片段支持的比例；
- `avg_semantic_support_rate`：已执行语义验证的问题中，主张被证据完整支持的平均比例；
- `repair_trigger_rate` / `repair_success_rate`：单次修复的触发率与成功率；
- `llm_repair_selection_rate`：首轮校验后真正需要 LLM 修复的比例；
- `deterministic_prune_selection_rate` / `repair_avoidance_rate`：可通过确定性裁剪处理、实际避免第二次生成的比例；
- `avg_latency_llm_repair_ms` / `avg_latency_without_llm_repair_ms`：修复路径与非修复路径的平均耗时，用于衡量修复调用的延迟成本；
- `final_refusal_rate` / `abstention_accuracy`：最终拒答率与应答/拒答判断准确率；
- `p95_latency_ms`：包含检索、生成、校验和可能修复的端到端 P95 延迟。

引用验证只检查引用编号与覆盖率，不等价于语义蕴含判断；语义质量继续由人工复核或 RAGAS Faithfulness 补充。

### `retrieval_eval_questions.json`

用于独立检索评测：

- 36 个问题；
- 28 个单文档召回问题，覆盖当前全部 28 份文档；
- 8 个跨文档召回问题；
- 以 PostgreSQL 中的 `doc_id` 作为相关性标识；
- 支持计算 Precision@K、Recall@K、MRR 和 nDCG@K。

该数据集与当前知识库快照绑定。如果删除后重新上传文档导致 `doc_id` 改变，必须同步更新相关性标注。

### `ragas_eval_questions.json`

用于 RAGAS 语义质量评测。当前版本已移除早期的轮毂识别、合格证 OCR
和示例扭矩报警题，改为基于 PostgreSQL 中状态为 `indexed` 的真实文档
及 `document_chunks` 原文建立的 30 道单轮金标题：20 道 LessonLearn 案例题和
10 道标准作业文档题，覆盖当前全部 28 份有效文档与 30 个直接证据 chunk。

题目按 `easy`、`medium`、`hard` 标注难度，并使用 `question_type` 区分根因、
措施、过程追溯、参数、检验和标准流程等场景。评测集中的参考答案不是模型自动生成结果，
而是根据绑定的原始 chunk 逐条整理；发布前仍需由熟悉业务的人员进行最终复核。

每道题包含：

- `reference_answer`：只根据原始 chunk 编写的参考答案；
- `expected_doc_ids`：预期召回的有效文档；
- `expected_chunk_ids`：参考答案对应的原始 chunk；
- `reference_contexts`：人工确认的核心证据摘要；
- `evaluation_type=single_turn_grounded`：表示该题必须隔离会话记忆。

RAGAS 运行时每题使用独立 `session_id`，并通过
`memory_enabled=false` 禁止读取、保存短期和长期记忆。评测报告会保存实际
`retrieved_contexts`、引用、查询改写、意图和证据判断结果，便于逐题定位。

如果知识库删除或重新上传文档导致 `doc_id`、`chunk_id` 改变，必须从数据库
重新核对证据并发布新的评测集版本，不能为了提高分数直接修改参考答案。

运行RAGAS前，先验证这些金标题能否召回预期文档：

```bash
python -m scripts.evaluate_ragas_retrieval --top-k 5 --k-values 1,3,5
python -m scripts.evaluate_ragas_retrieval --relevance-field chunk_id --top-k 5 --k-values 1,3,5
```

失败题可以通过 `--question-ids` 做低成本定向回归，例如：

```bash
python -m scripts.evaluate_ragas_retrieval --relevance-field chunk_id --question-ids KB-STD-001,KB-STD-009 --top-k 5 --k-values 1,3,5
```

该命令只执行当前在线检索，不调用答案生成模型或RAGAS评审模型。

## 推荐运行顺序

先运行独立检索评测，不调用问答 LLM：

```bash
python -m scripts.evaluate_retrieval --dataset data/eval/retrieval_eval_questions.json --top-k 5 --k-values 1,3,5
```

确认 Recall@5、MRR 和 nDCG@5 后，再运行端到端问答评测：

```bash
python -m scripts.evaluate_system
```

Docker 环境：

```bash
docker compose exec api python -m scripts.evaluate_retrieval --dataset data/eval/retrieval_eval_questions.json --top-k 5 --k-values 1,3,5
docker compose exec api python -m scripts.evaluate_system
```

React 看板支持先运行 5 题或 10 题小样本，再运行完整 44 题。API 也支持限制规模：

```bash
curl -X POST http://localhost:8000/api/v1/evaluation/run \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"max_questions": 10}'
```

每次新生成的评估报告还包含 `failure_analysis`：

- `failure_categories`：每题的主失败阶段；
- `failure_tags`：允许一个问题同时记录召回、拒答、引用等多个问题；
- `false_refusal_rate`：可回答问题被系统拒答的比例；
- `knowledge_gap_refusal_accuracy`：知识缺口问题的正确拒答比例；
- `evidence_threshold_sweep`：比较多个证据阈值下的错误拒答率和错误放行率。

阈值扫描用于校准，不会自动修改 `EVIDENCE_CONFIDENCE_THRESHOLD`。必须结合知识缺口样本和人工检查后再调整线上阈值。

`answer_keyword_hit_rate` 只以可回答问题为分母；知识缺口题以是否正确拒答为准，不再因为拒答文案没有逐字匹配某个提示词而判定失败。

## 人工复核规则

第一轮运行后，应逐条复核失败项，不能直接通过修改期望结果让指标变好：

1. 目标文档是否确实包含答案；
2. 问题是否存在歧义；
3. `expected_keywords` 是否只包含文档中可验证的事实；
4. 跨文档问题是否在 Top 5 的容量范围内设置了过多相关文档；
5. 知识缺口问题是否明确拒答，而不是生成未经引用支持的参数；
6. 对 4 个配置了 `followup_question` 与 `expected_followup_keywords` 的问题，检查多轮追问是否真正使用前文主题，同时保留当前轮检索引用。

第一版是基线而不是最终真值集。建议人工审阅后冻结为 `baseline-v1`，后续通过新版本文件演进，不覆盖已经用于指标对比的历史快照。
