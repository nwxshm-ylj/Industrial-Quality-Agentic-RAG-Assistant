# GitHub 发布文件清单

本清单基于 2026-08-28 的本地唯一代码源 `C:\\cursor-projects\\2-Industrial-RAG`。仅列出本次需要纳入提交的实质差异和新增文件；已跟踪且没有实质补丁的源码仍会随仓库发布，无需重复 `git add`。

## 批次 0：发布边界与已暂存上传删除

先创建发布分支，然后提交忽略规则、换行规则、4 个应从索引移除但保留在本机的文件，以及当前已经暂存的 46 项 `data/uploads` 删除。不要恢复或改写这些上传文件。

```powershell
cd C:\cursor-projects\2-Industrial-RAG
git switch -c codex/release-v1-prep
git add -- .gitignore .gitattributes
git rm --cached -- PROJECT_ANALYSIS_AND_ROADMAP.md data/eval/eval_report.json data/eval/eval_report_c62c1a56-8f4d-4e9e-b262-9c65a6669411.json docs/interview_notes.md
git commit -m "chore: exclude runtime and private artifacts"
```

该提交会同时包含以下 46 项当前已暂存删除：

- `data/uploads/2a5bf4918ab44ee49d30d01116e06cde_测试.txt`
- `data/uploads/3145278e6c314210b4db5826e7407817_百面机器学习_算法工程师带你去面试.pdf`
- `data/uploads/797a50fbcaec4f1793761fc7a787100a_2026-07-07_今日知识点整理.md`
- `data/uploads/8c9452814f7a44f8a351c4323800b4b7_MD32NKE1操作键盘用户手册-CN-A02.pdf`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0001.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0002.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0003.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0004.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0005.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0006.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0007.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0008.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0009.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0010.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0011.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0012.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0013.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0014.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0015.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0016.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0017.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0018.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0019.png`
- `data/uploads/assets/8c9452814f7a44f8a351c4323800b4b7/initial/8c9452814f7a44f8a351c4323800b4b7_page_0020.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0001.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0002.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0003.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0004.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0005.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0006.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0007.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0008.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0009.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0010.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0011.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0012.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0013.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0014.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0015.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0016.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0017.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0018.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0019.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0020.png`
- `data/uploads/assets/fa910224023440cb8d242daf11325bd8/initial/fa910224023440cb8d242daf11325bd8_page_0021.png`
- `data/uploads/fa910224023440cb8d242daf11325bd8_MD38IO2_I_O扩展卡用户手册-CN-A02.pdf`

## 批次 1：后端、LangGraph、检索与可信生成

共 58 个文件。

```powershell
$files = @(
    'app/api/routes_chat.py'
    'app/api/routes_diagnostics.py'
    'app/api/routes_documents.py'
    'app/api/routes_evaluation.py'
    'app/core/config.py'
    'app/core/metrics.py'
    'app/core/telemetry_context.py'
    'app/evaluation/generation_analysis.py'
    'app/evaluation/ragas_compat.py'
    'app/evaluation/ragas_evaluator.py'
    'app/generation/__init__.py'
    'app/generation/abstention.py'
    'app/generation/citation_validator.py'
    'app/generation/semantic_citation_validator.py'
    'app/graph/nodes/answer_repair_node.py'
    'app/graph/nodes/answer_verifier_node.py'
    'app/graph/nodes/context_builder_node.py'
    'app/graph/nodes/evidence_judge_node.py'
    'app/graph/nodes/finalize_answer_node.py'
    'app/graph/nodes/generate_node.py'
    'app/graph/nodes/intent_router_node.py'
    'app/graph/nodes/load_memory_node.py'
    'app/graph/nodes/query_rewriter_node.py'
    'app/graph/nodes/retrieve_node.py'
    'app/graph/nodes/save_memory_node.py'
    'app/graph/query_features.py'
    'app/graph/state.py'
    'app/graph/workflow.py'
    'app/knowledge_graph/base.py'
    'app/knowledge_graph/neo4j_backend.py'
    'app/knowledge_graph/service.py'
    'app/main.py'
    'app/observability/request_diagnostics.py'
    'app/observability/usage_models.py'
    'app/rag/generator.py'
    'app/rag/graph_chain.py'
    'app/rag/online_hybrid_retriever.py'
    'app/rag/reranker.py'
    'app/rag/retrieval_filters.py'
    'app/rag/retriever.py'
    'app/rag/search_backends/multimodal_qdrant_backend.py'
    'app/rag/search_backends/opensearch_backend.py'
    'app/rag/search_backends/qdrant_backend.py'
    'app/rag/splitter.py'
    'app/schemas/chat.py'
    'app/schemas/document.py'
    'app/schemas/evaluation.py'
    'app/schemas/observability.py'
    'app/services/document_service.py'
    'app/services/evaluation_service.py'
    'app/services/ragas_evaluation_service.py'
    'app/services/usage_service.py'
    'app/streaming/__init__.py'
    'app/streaming/events.py'
    'app/traceability/__init__.py'
    'app/traceability/entity_linker.py'
    'app/traceability/service.py'
    'app/traceability/taxonomy.py'
)
git add -- $files
git commit -m "feat: complete industrial rag backend and trust controls"
```

文件：

- `app/api/routes_chat.py`
- `app/api/routes_diagnostics.py`
- `app/api/routes_documents.py`
- `app/api/routes_evaluation.py`
- `app/core/config.py`
- `app/core/metrics.py`
- `app/core/telemetry_context.py`
- `app/evaluation/generation_analysis.py`
- `app/evaluation/ragas_compat.py`
- `app/evaluation/ragas_evaluator.py`
- `app/generation/__init__.py`
- `app/generation/abstention.py`
- `app/generation/citation_validator.py`
- `app/generation/semantic_citation_validator.py`
- `app/graph/nodes/answer_repair_node.py`
- `app/graph/nodes/answer_verifier_node.py`
- `app/graph/nodes/context_builder_node.py`
- `app/graph/nodes/evidence_judge_node.py`
- `app/graph/nodes/finalize_answer_node.py`
- `app/graph/nodes/generate_node.py`
- `app/graph/nodes/intent_router_node.py`
- `app/graph/nodes/load_memory_node.py`
- `app/graph/nodes/query_rewriter_node.py`
- `app/graph/nodes/retrieve_node.py`
- `app/graph/nodes/save_memory_node.py`
- `app/graph/query_features.py`
- `app/graph/state.py`
- `app/graph/workflow.py`
- `app/knowledge_graph/base.py`
- `app/knowledge_graph/neo4j_backend.py`
- `app/knowledge_graph/service.py`
- `app/main.py`
- `app/observability/request_diagnostics.py`
- `app/observability/usage_models.py`
- `app/rag/generator.py`
- `app/rag/graph_chain.py`
- `app/rag/online_hybrid_retriever.py`
- `app/rag/reranker.py`
- `app/rag/retrieval_filters.py`
- `app/rag/retriever.py`
- `app/rag/search_backends/multimodal_qdrant_backend.py`
- `app/rag/search_backends/opensearch_backend.py`
- `app/rag/search_backends/qdrant_backend.py`
- `app/rag/splitter.py`
- `app/schemas/chat.py`
- `app/schemas/document.py`
- `app/schemas/evaluation.py`
- `app/schemas/observability.py`
- `app/services/document_service.py`
- `app/services/evaluation_service.py`
- `app/services/ragas_evaluation_service.py`
- `app/services/usage_service.py`
- `app/streaming/__init__.py`
- `app/streaming/events.py`
- `app/traceability/__init__.py`
- `app/traceability/entity_linker.py`
- `app/traceability/service.py`
- `app/traceability/taxonomy.py`

## 批次 2：Prompt、评测集与验证脚本

共 67 个文件；仅保留命名基线 `eval_report_g34_baseline.json`，不包含通用或 UUID 运行报告。

```powershell
$files = @(
    'data/eval/README.md'
    'data/eval/eval_questions.json'
    'data/eval/eval_report_g34_baseline.json'
    'data/eval/ragas_eval_questions.json'
    'data/eval/retrieval_eval_questions.json'
    'prompts/catalog/industrial.answer_generator/1.1.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.2.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.3.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.4.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.5.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.6.0.yaml'
    'prompts/catalog/industrial.answer_generator/1.7.0.yaml'
    'prompts/catalog/industrial.answer_repair/1.0.0.yaml'
    'prompts/catalog/industrial.answer_repair/1.1.0.yaml'
    'prompts/catalog/industrial.intent_router/1.1.0.yaml'
    'prompts/catalog/industrial.query_rewriter.initial/1.1.0.yaml'
    'prompts/catalog/industrial.query_rewriter.retry/1.1.0.yaml'
    'prompts/catalog/industrial.semantic_citation_verifier/1.0.0.yaml'
    'prompts/releases/candidate.yaml'
    'prompts/releases/industrial-prompts-2026-07-14.1.yaml'
    'prompts/releases/industrial-prompts-2026-08-26.1.yaml'
    'prompts/releases/industrial-prompts-2026-08-27.2.yaml'
    'prompts/releases/industrial-prompts-2026-08-27.3.yaml'
    'prompts/releases/stable.yaml'
    'scripts/analyze_generation_report.py'
    'scripts/backfill_document_graph.py'
    'scripts/compare_generation_reports.py'
    'scripts/configure_local_embedding.py'
    'scripts/diagnose_retrieval_evidence.py'
    'scripts/evaluate_ragas_retrieval.py'
    'scripts/evaluate_system.py'
    'scripts/init_sql_data.py'
    'scripts/test_answer_repair_flow.py'
    'scripts/test_answer_validation.py'
    'scripts/test_auth_rbac.py'
    'scripts/test_case_retrieval_loop.py'
    'scripts/test_context_builder.py'
    'scripts/test_document_logging.py'
    'scripts/test_document_management.py'
    'scripts/test_evidence_judge.py'
    'scripts/test_generation_analysis.py'
    'scripts/test_generation_evaluation_metrics.py'
    'scripts/test_generation_guard.py'
    'scripts/test_generation_repair_policy.py'
    'scripts/test_generation_report_comparison.py'
    'scripts/test_generation_trust_p0.py'
    'scripts/test_intent.py'
    'scripts/test_knowledge_graph.py'
    'scripts/test_multimodal_qdrant_backend.py'
    'scripts/test_online_hybrid_retriever.py'
    'scripts/test_opensearch_keyword_backend.py'
    'scripts/test_prompt_components_mock.py'
    'scripts/test_prompt_registry.py'
    'scripts/test_prompt_rendering.py'
    'scripts/test_qdrant_vector_backend.py'
    'scripts/test_query_task_modes.py'
    'scripts/test_ragas_evaluation.py'
    'scripts/test_ragas_evaluation_isolation.py'
    'scripts/test_ragas_langchain_compat.py'
    'scripts/test_request_diagnostics.py'
    'scripts/test_reranker_metadata.py'
    'scripts/test_semantic_abstention.py'
    'scripts/test_semantic_citation_validation.py'
    'scripts/test_streaming.py'
    'scripts/test_traceability.py'
    'scripts/validate_prompts.py'
    'scripts/validate_ragas_dataset.py'
)
git add -- $files
git commit -m "test: add prompts evaluation assets and regressions"
```

文件：

- `data/eval/README.md`
- `data/eval/eval_questions.json`
- `data/eval/eval_report_g34_baseline.json`
- `data/eval/ragas_eval_questions.json`
- `data/eval/retrieval_eval_questions.json`
- `prompts/catalog/industrial.answer_generator/1.1.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.2.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.3.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.4.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.5.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.6.0.yaml`
- `prompts/catalog/industrial.answer_generator/1.7.0.yaml`
- `prompts/catalog/industrial.answer_repair/1.0.0.yaml`
- `prompts/catalog/industrial.answer_repair/1.1.0.yaml`
- `prompts/catalog/industrial.intent_router/1.1.0.yaml`
- `prompts/catalog/industrial.query_rewriter.initial/1.1.0.yaml`
- `prompts/catalog/industrial.query_rewriter.retry/1.1.0.yaml`
- `prompts/catalog/industrial.semantic_citation_verifier/1.0.0.yaml`
- `prompts/releases/candidate.yaml`
- `prompts/releases/industrial-prompts-2026-07-14.1.yaml`
- `prompts/releases/industrial-prompts-2026-08-26.1.yaml`
- `prompts/releases/industrial-prompts-2026-08-27.2.yaml`
- `prompts/releases/industrial-prompts-2026-08-27.3.yaml`
- `prompts/releases/stable.yaml`
- `scripts/analyze_generation_report.py`
- `scripts/backfill_document_graph.py`
- `scripts/compare_generation_reports.py`
- `scripts/configure_local_embedding.py`
- `scripts/diagnose_retrieval_evidence.py`
- `scripts/evaluate_ragas_retrieval.py`
- `scripts/evaluate_system.py`
- `scripts/init_sql_data.py`
- `scripts/test_answer_repair_flow.py`
- `scripts/test_answer_validation.py`
- `scripts/test_auth_rbac.py`
- `scripts/test_case_retrieval_loop.py`
- `scripts/test_context_builder.py`
- `scripts/test_document_logging.py`
- `scripts/test_document_management.py`
- `scripts/test_evidence_judge.py`
- `scripts/test_generation_analysis.py`
- `scripts/test_generation_evaluation_metrics.py`
- `scripts/test_generation_guard.py`
- `scripts/test_generation_repair_policy.py`
- `scripts/test_generation_report_comparison.py`
- `scripts/test_generation_trust_p0.py`
- `scripts/test_intent.py`
- `scripts/test_knowledge_graph.py`
- `scripts/test_multimodal_qdrant_backend.py`
- `scripts/test_online_hybrid_retriever.py`
- `scripts/test_opensearch_keyword_backend.py`
- `scripts/test_prompt_components_mock.py`
- `scripts/test_prompt_registry.py`
- `scripts/test_prompt_rendering.py`
- `scripts/test_qdrant_vector_backend.py`
- `scripts/test_query_task_modes.py`
- `scripts/test_ragas_evaluation.py`
- `scripts/test_ragas_evaluation_isolation.py`
- `scripts/test_ragas_langchain_compat.py`
- `scripts/test_request_diagnostics.py`
- `scripts/test_reranker_metadata.py`
- `scripts/test_semantic_abstention.py`
- `scripts/test_semantic_citation_validation.py`
- `scripts/test_streaming.py`
- `scripts/test_traceability.py`
- `scripts/validate_prompts.py`
- `scripts/validate_ragas_dataset.py`

## 批次 3：React 前端

共 45 个文件。

```powershell
$files = @(
    'frontend/src/api/chat.test.ts'
    'frontend/src/api/chat.ts'
    'frontend/src/api/documents.test.ts'
    'frontend/src/api/documents.ts'
    'frontend/src/api/evaluation.test.ts'
    'frontend/src/api/evaluation.ts'
    'frontend/src/api/generated/schema.d.ts'
    'frontend/src/api/observability.test.ts'
    'frontend/src/api/observability.ts'
    'frontend/src/api/types.ts'
    'frontend/src/design/antdTheme.ts'
    'frontend/src/design/tokens.ts'
    'frontend/src/features/chat/ChatComposer.test.tsx'
    'frontend/src/features/chat/ChatComposer.tsx'
    'frontend/src/features/chat/ConversationTurn.tsx'
    'frontend/src/features/chat/EvidencePanel.tsx'
    'frontend/src/features/chat/imageAttachments.test.ts'
    'frontend/src/features/chat/imageAttachments.ts'
    'frontend/src/features/chat/markdown.test.ts'
    'frontend/src/features/chat/markdown.ts'
    'frontend/src/features/chat/presentation.test.ts'
    'frontend/src/features/chat/presentation.ts'
    'frontend/src/features/diagnostics/AnswerDiagnosisDrawer.tsx'
    'frontend/src/features/diagnostics/DiagnosticSnapshotView.tsx'
    'frontend/src/features/diagnostics/diagnostics.test.ts'
    'frontend/src/features/diagnostics/diagnostics.ts'
    'frontend/src/features/evaluation/EvaluationDetailDrawer.tsx'
    'frontend/src/features/evaluation/presentation.test.ts'
    'frontend/src/features/evaluation/presentation.ts'
    'frontend/src/features/knowledge-base/DocumentDetailDrawer.tsx'
    'frontend/src/features/knowledge-base/DocumentUploadPanel.tsx'
    'frontend/src/features/knowledge-base/presentation.test.ts'
    'frontend/src/features/knowledge-base/presentation.ts'
    'frontend/src/features/observability/RequestDetailsDrawer.tsx'
    'frontend/src/layout/AppShell.tsx'
    'frontend/src/main.tsx'
    'frontend/src/pages/ChatPage.tsx'
    'frontend/src/pages/DashboardPage.tsx'
    'frontend/src/pages/EvaluationPage.tsx'
    'frontend/src/pages/KnowledgeBasePage.tsx'
    'frontend/src/pages/ObservabilityPage.tsx'
    'frontend/src/stores/chatStore.test.ts'
    'frontend/src/stores/chatStore.ts'
    'frontend/src/styles/design-system.css'
    'frontend/src/styles/global.css'
)
git add -- $files
git commit -m "feat: update react operations console"
```

文件：

- `frontend/src/api/chat.test.ts`
- `frontend/src/api/chat.ts`
- `frontend/src/api/documents.test.ts`
- `frontend/src/api/documents.ts`
- `frontend/src/api/evaluation.test.ts`
- `frontend/src/api/evaluation.ts`
- `frontend/src/api/generated/schema.d.ts`
- `frontend/src/api/observability.test.ts`
- `frontend/src/api/observability.ts`
- `frontend/src/api/types.ts`
- `frontend/src/design/antdTheme.ts`
- `frontend/src/design/tokens.ts`
- `frontend/src/features/chat/ChatComposer.test.tsx`
- `frontend/src/features/chat/ChatComposer.tsx`
- `frontend/src/features/chat/ConversationTurn.tsx`
- `frontend/src/features/chat/EvidencePanel.tsx`
- `frontend/src/features/chat/imageAttachments.test.ts`
- `frontend/src/features/chat/imageAttachments.ts`
- `frontend/src/features/chat/markdown.test.ts`
- `frontend/src/features/chat/markdown.ts`
- `frontend/src/features/chat/presentation.test.ts`
- `frontend/src/features/chat/presentation.ts`
- `frontend/src/features/diagnostics/AnswerDiagnosisDrawer.tsx`
- `frontend/src/features/diagnostics/DiagnosticSnapshotView.tsx`
- `frontend/src/features/diagnostics/diagnostics.test.ts`
- `frontend/src/features/diagnostics/diagnostics.ts`
- `frontend/src/features/evaluation/EvaluationDetailDrawer.tsx`
- `frontend/src/features/evaluation/presentation.test.ts`
- `frontend/src/features/evaluation/presentation.ts`
- `frontend/src/features/knowledge-base/DocumentDetailDrawer.tsx`
- `frontend/src/features/knowledge-base/DocumentUploadPanel.tsx`
- `frontend/src/features/knowledge-base/presentation.test.ts`
- `frontend/src/features/knowledge-base/presentation.ts`
- `frontend/src/features/observability/RequestDetailsDrawer.tsx`
- `frontend/src/layout/AppShell.tsx`
- `frontend/src/main.tsx`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/EvaluationPage.tsx`
- `frontend/src/pages/KnowledgeBasePage.tsx`
- `frontend/src/pages/ObservabilityPage.tsx`
- `frontend/src/stores/chatStore.test.ts`
- `frontend/src/stores/chatStore.ts`
- `frontend/src/styles/design-system.css`
- `frontend/src/styles/global.css`

## 批次 4：配置、正式文档、Streamlit 与仓库 Skills

共 19 个文件。

```powershell
$files = @(
    '.agents/skills/code-review/SKILL.md'
    '.agents/skills/knowledge-base-lifecycle/SKILL.md'
    '.agents/skills/online-hybrid-search/SKILL.md'
    '.agents/skills/project-onboarding/SKILL.md'
    '.agents/skills/regression-validation/SKILL.md'
    '.env.example'
    '.env.production.example'
    'DESIGN.md'
    'README.md'
    'docker-compose.yml'
    'docs/api_examples.md'
    'docs/architecture.md'
    'docs/demo_script.md'
    'docs/deployment.md'
    'docs/github-release-file-manifest.md'
    'docs/observability.md'
    'docs/rag-troubleshooting.md'
    'requirements.txt'
    'ui/streamlit_app.py'
)
git add -- $files
git commit -m "docs: prepare public github release"
```

文件：

- `.agents/skills/code-review/SKILL.md`
- `.agents/skills/knowledge-base-lifecycle/SKILL.md`
- `.agents/skills/online-hybrid-search/SKILL.md`
- `.agents/skills/project-onboarding/SKILL.md`
- `.agents/skills/regression-validation/SKILL.md`
- `.env.example`
- `.env.production.example`
- `DESIGN.md`
- `README.md`
- `docker-compose.yml`
- `docs/api_examples.md`
- `docs/architecture.md`
- `docs/demo_script.md`
- `docs/deployment.md`
- `docs/github-release-file-manifest.md`
- `docs/observability.md`
- `docs/rag-troubleshooting.md`
- `requirements.txt`
- `ui/streamlit_app.py`

## 明确排除

以下内容不得加入上述批次：

- `data/uploads/**` 的本地内容（仅保留当前 46 项删除）
- `data/models/**`、`data/model_cache/**`、`models/**`、`huggingface/**`、`hf_cache/**`
- `__pycache__/**`、`*.pyc`、`.pytest_cache/**`、`.ruff_cache/**`、`frontend/node_modules/**`、`frontend/dist/**`
- `tmp/**`、`.tmp/**`、`deliverables/**`、`reports/**`
- `data/eval/eval_report.json`、`data/eval/eval_report_<UUID>.json` 及其他运行时/诊断报告
- `PROJECT_ANALYSIS_AND_ROADMAP.md`
- `docs/codex_handoff.md`、`docs/interview_notes.md`、`docs/interview/**`、`docs/project-technical-interview-guide.md`
- `.env`、`.env.production` 及任何真实密码、Token、API Key

## 每批提交后复核

```powershell
git diff --cached --check
git status --short
git diff --cached --name-only
```

全部提交后：

```powershell
git update-index --refresh
git diff --check
git status --short
git log --oneline --decorate -12
git push -u origin codex/release-v1-prep
```

如果 `git update-index --refresh` 后仍显示文件为修改，但 `git diff -- <file>` 为空，不要把该文件加入提交；这属于当前 Windows 换行/stat 状态噪声。

