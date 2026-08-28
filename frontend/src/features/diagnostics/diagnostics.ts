import type {
  ChatResponse,
  DiagnosticCheck,
  DiagnosticContext,
  RequestDiagnosticSnapshot,
} from "../../api/types";

const diagnosticFields = ["根本原因", "原因", "措施", "对策", "状态", "结果"];

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function hasEmptyFieldConflict(answer: string, evidenceText: string): boolean {
  return diagnosticFields.some((field) => {
    const escaped = escapeRegExp(field);
    const emptyPattern = new RegExp(`${escaped}.{0,12}(?:为空|未填写|无记录|未记录)`, "i");
    const evidencePattern = new RegExp(`${escaped}(?:栏)?\\s*[:：]\\s*(?!为空|未填写|无记录|未记录)\\S+`, "i");
    return emptyPattern.test(answer) && evidencePattern.test(evidenceText);
  });
}

function contextSummary(value: Record<string, unknown>, rank: number): DiagnosticContext {
  return {
    ...value,
    rank,
    text_excerpt: typeof value.text === "string" ? value.text : null,
  };
}

function citationSummary(value: Record<string, unknown>, rank: number): DiagnosticContext {
  return { ...value, rank };
}

function check(
  code: string,
  status: DiagnosticCheck["status"],
  title: string,
  detail: string,
  stage: string,
): DiagnosticCheck {
  return { code, status, title, detail, stage };
}

export function buildLocalDiagnosticSnapshot(response: ChatResponse): RequestDiagnosticSnapshot {
  const contexts = (response.contexts || []).map((item, index) => (
    contextSummary(item as Record<string, unknown>, index + 1)
  ));
  const citations = (response.citations || []).map((item, index) => (
    citationSummary(item as unknown as Record<string, unknown>, index + 1)
  ));
  const metadata = response.metadata || {};
  const checks: DiagnosticCheck[] = [];

  checks.push(contexts.length
    ? check("retrieval_has_context", "pass", "检索已返回上下文", `当前响应包含 ${contexts.length} 条上下文。`, "retrieval")
    : check("retrieval_has_context", "fail", "最终检索结果为空", "优先检查解析、索引、过滤条件和召回服务。", "retrieval"));

  checks.push(metadata.degraded === true
    ? check("retrieval_degraded", "warning", "检索发生降级", String(metadata.degraded_reason || "部分检索组件不可用。"), "retrieval")
    : check("retrieval_degraded", "pass", "未记录检索降级", "当前响应未标记 degraded。", "retrieval"));

  if (contexts.length && !citations.length) {
    checks.push(check("citation_missing", "fail", "有上下文但无引用", "检查引用映射和最终回答整理逻辑。", "citation"));
  } else if (citations.length) {
    checks.push(check("citation_present", "pass", "引用映射已生成", `共 ${citations.length} 条引用。`, "citation"));
  }

  const incompleteBundles = contexts.filter((item) => (
    Number(item.evidence_chunk_count || 0) > (item.evidence_chunk_ids?.length || 0)
  ));
  if (incompleteBundles.length) {
    checks.push(check(
      "evidence_bundle_incomplete",
      "warning",
      "证据包片段记录不完整",
      "evidence_chunk_count 大于 evidence_chunk_ids 数量。",
      "traceability",
    ));
  }

  const evidenceText = contexts.map((item) => item.text_excerpt || "").join("\n");
  if (hasEmptyFieldConflict(response.answer || "", evidenceText)) {
    checks.push(check(
      "possible_empty_field_conflict",
      "warning",
      "回答的空值结论可能与证据冲突",
      "回答声称字段为空，但当前上下文检测到同类字段的非空结构，请人工核对。",
      "generation",
    ));
  }

  if (response.evidence_enough === false || metadata.evidence_enough === false) {
    checks.push(check(
      "evidence_not_enough",
      "warning",
      "证据充分性未通过",
      "检查缺失字段、检索范围和拒答原因。",
      "evidence_judge",
    ));
  }

  return {
    schema_version: "local-1.0",
    captured_at: new Date().toISOString(),
    status: "success",
    content_capture_enabled: true,
    routing: {
      intent: response.intent || metadata.intent,
      task_mode: response.task_mode,
      requested_retrieval_mode: response.retrieval_mode,
      retrieval_mode: metadata.retrieval_mode,
      rewritten_query: response.rewritten_query,
    },
    retrieval: {
      metadata,
      candidates: {},
      final_contexts: contexts,
    },
    generation: {
      context_metadata: {
        generation_context_count: metadata.generation_context_count,
        input_context_count: metadata.input_context_count,
      },
      contexts,
      citations,
      answer_excerpt: response.answer,
      evidence_enough: response.evidence_enough ?? metadata.evidence_enough,
      evidence_confidence: typeof metadata.evidence_confidence === "number"
        ? metadata.evidence_confidence
        : null,
      generation_quality_passed: typeof metadata.generation_quality_passed === "boolean"
        ? metadata.generation_quality_passed
        : null,
      answer_abstained: typeof metadata.answer_abstained === "boolean"
        ? metadata.answer_abstained
        : null,
      validation: (metadata.answer_validation as Record<string, unknown> | undefined) || {},
    },
    versions: {
      prompt_release: metadata.prompt_release,
      prompt_versions: metadata.prompt_versions,
    },
    checks,
  };
}

export function diagnosticStatusLabel(status: DiagnosticCheck["status"]): string {
  return {
    pass: "通过",
    warning: "关注",
    fail: "异常",
    info: "说明",
  }[status];
}

export function diagnosticStatusColor(status: DiagnosticCheck["status"]): string {
  return {
    pass: "success",
    warning: "warning",
    fail: "error",
    info: "processing",
  }[status];
}
