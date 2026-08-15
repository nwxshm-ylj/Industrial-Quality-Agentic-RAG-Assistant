import { Descriptions, Drawer, Empty, Table, Tag, Typography, type TableColumnsType } from "antd";

import type { EvalItemInfo, EvalRunResponse, RetrievalEvalRunResponse } from "../../api/types";
import { formatDocumentDate } from "../knowledge-base/presentation";
import { formatRate, getGenerationMetric, getRetrievalK, getRetrievalMetric } from "./presentation";

interface EvaluationDetailDrawerProps {
  open: boolean;
  kind: "generation" | "retrieval" | null;
  loading: boolean;
  generation?: EvalRunResponse;
  retrieval?: RetrievalEvalRunResponse;
  onClose: () => void;
}

const itemColumns: TableColumnsType<EvalItemInfo> = [
  { title: "问题", dataIndex: "question", width: 260, ellipsis: true },
  { title: "期望意图", dataIndex: "expected_intent", width: 110 },
  { title: "实际意图", dataIndex: "actual_intent", width: 110 },
  { title: "关键词", dataIndex: "keyword_hit", width: 80, render: (value) => value == null ? "--" : value ? "✓" : "×" },
  { title: "来源", dataIndex: "source_hit", width: 70, render: (value) => value == null ? "--" : value ? "✓" : "×" },
  { title: "引用", dataIndex: "citation_contract_ok", width: 70, render: (value) => value == null ? "--" : value ? "✓" : "×" },
  { title: "覆盖率", dataIndex: "citation_coverage", width: 85, render: formatRate },
  { title: "语义支持", dataIndex: "semantic_support_ok", width: 90, render: (value) => value == null ? "--" : value ? "✓" : "×" },
  { title: "支持率", dataIndex: "semantic_support_rate", width: 85, render: formatRate },
  { title: "校验动作", dataIndex: "validation_action", width: 130, render: (value) => value || "--" },
  { title: "修复", dataIndex: "generation_retry_count", width: 65 },
  { title: "裁剪", dataIndex: "citation_pruned", width: 65, render: (value) => value ? "是" : "否" },
  { title: "证据分", dataIndex: "evidence_confidence", width: 80, render: (value) => value == null ? "--" : Number(value).toFixed(3) },
  { title: "失败归因", dataIndex: "failure_category", width: 145, render: (value) => value || "--" },
  { title: "拒答", dataIndex: "answer_abstained", width: 65, render: (value) => value ? "是" : "否" },
  { title: "结果", dataIndex: "passed", width: 75, render: (value) => <Tag color={value ? "success" : "error"} bordered={false}>{value ? "PASS" : "FAIL"}</Tag> },
];

export function EvaluationDetailDrawer({
  open,
  kind,
  loading,
  generation,
  retrieval,
  onClose,
}: EvaluationDetailDrawerProps) {
  return (
    <Drawer
      width={720}
      open={open}
      loading={loading}
      onClose={onClose}
      title={(
        <div>
          <Typography.Text className="panel-kicker">EVALUATION RUN</Typography.Text>
          <Typography.Title level={4}>{kind === "retrieval" ? "检索评估详情" : "生成式评估详情"}</Typography.Title>
        </div>
      )}
    >
      {kind === "generation" && generation && (
        <div className="eval-detail-stack">
          <Descriptions column={2} colon={false} bordered size="small">
            <Descriptions.Item label="Run ID" span={2}>{generation.run_id}</Descriptions.Item>
            <Descriptions.Item label="状态">{generation.status}</Descriptions.Item>
            <Descriptions.Item label="问题数">{generation.total_questions}</Descriptions.Item>
            <Descriptions.Item label="意图准确率">{formatRate(generation.intent_accuracy)}</Descriptions.Item>
            <Descriptions.Item label="来源命中率">{formatRate(generation.source_hit_rate)}</Descriptions.Item>
            <Descriptions.Item label="关键词命中率">{formatRate(generation.answer_keyword_hit_rate)}</Descriptions.Item>
            <Descriptions.Item label="记忆追问成功率">{formatRate(generation.memory_followup_success_rate)}</Descriptions.Item>
            <Descriptions.Item label="总体通过率">{formatRate(getGenerationMetric(generation, "overall_pass_rate"))}</Descriptions.Item>
            <Descriptions.Item label="引用验证通过率">{formatRate(getGenerationMetric(generation, "citation_validation_pass_rate"))}</Descriptions.Item>
            <Descriptions.Item label="平均引用覆盖率">{formatRate(getGenerationMetric(generation, "avg_citation_coverage"))}</Descriptions.Item>
            <Descriptions.Item label="语义验证覆盖率">{formatRate(getGenerationMetric(generation, "semantic_validation_coverage_rate"))}</Descriptions.Item>
            <Descriptions.Item label="语义支持通过率">{formatRate(getGenerationMetric(generation, "semantic_support_pass_rate"))}</Descriptions.Item>
            <Descriptions.Item label="平均语义支持率">{formatRate(getGenerationMetric(generation, "avg_semantic_support_rate"))}</Descriptions.Item>
            <Descriptions.Item label="修复触发率">{formatRate(getGenerationMetric(generation, "repair_trigger_rate"))}</Descriptions.Item>
            <Descriptions.Item label="LLM 修复选择率">{formatRate(getGenerationMetric(generation, "llm_repair_selection_rate"))}</Descriptions.Item>
            <Descriptions.Item label="确定性裁剪选择率">{formatRate(getGenerationMetric(generation, "deterministic_prune_selection_rate"))}</Descriptions.Item>
            <Descriptions.Item label="避免修复率">{formatRate(getGenerationMetric(generation, "repair_avoidance_rate"))}</Descriptions.Item>
            <Descriptions.Item label="修复成功率">{formatRate(getGenerationMetric(generation, "repair_success_rate"))}</Descriptions.Item>
            <Descriptions.Item label="拒答准确率">{formatRate(getGenerationMetric(generation, "abstention_accuracy"))}</Descriptions.Item>
            <Descriptions.Item label="最终拒答率">{formatRate(getGenerationMetric(generation, "final_refusal_rate"))}</Descriptions.Item>
            <Descriptions.Item label="P95 延迟">{getGenerationMetric(generation, "p95_latency_ms").toFixed(0)} ms</Descriptions.Item>
            <Descriptions.Item label="错误拒答率">{formatRate(generation.failure_analysis?.false_refusal_rate || 0)}</Descriptions.Item>
            <Descriptions.Item label="确定性引用裁剪率">{formatRate(getGenerationMetric(generation, "deterministic_citation_pruning_rate"))}</Descriptions.Item>
            <Descriptions.Item label="修复路径平均耗时">{getGenerationMetric(generation, "avg_latency_llm_repair_ms").toFixed(0)} ms</Descriptions.Item>
            <Descriptions.Item label="非修复路径平均耗时">{getGenerationMetric(generation, "avg_latency_without_llm_repair_ms").toFixed(0)} ms</Descriptions.Item>
          </Descriptions>
          {generation.failure_analysis?.failure_categories && (
            <Descriptions title="失败归因" column={2} colon={false} bordered size="small">
              {Object.entries(generation.failure_analysis.failure_categories).map(([name, count]) => (
                <Descriptions.Item key={name} label={name}>{count}</Descriptions.Item>
              ))}
            </Descriptions>
          )}
          {generation.failure_analysis?.evidence_threshold_sweep?.length ? (
            <Table
              rowKey="threshold"
              size="small"
              pagination={false}
              dataSource={generation.failure_analysis.evidence_threshold_sweep}
              columns={[
                { title: "证据阈值", dataIndex: "threshold", render: (value) => Number(value).toFixed(2) },
                { title: "样本数", dataIndex: "sample_count" },
                { title: "决策准确率", dataIndex: "decision_accuracy", render: formatRate },
                { title: "错误拒答率", dataIndex: "false_refusal_rate", render: formatRate },
                { title: "错误放行率", dataIndex: "unsafe_answer_rate", render: formatRate },
              ]}
            />
          ) : null}
          {generation.items?.length ? (
            <Table rowKey="id" columns={itemColumns} dataSource={generation.items} scroll={{ x: 1450 }} pagination={{ pageSize: 8 }} />
          ) : <Empty description="该运行没有 item 明细" />}
        </div>
      )}

      {kind === "retrieval" && retrieval && (
        <div className="eval-detail-stack">
          <Descriptions column={2} colon={false} bordered size="small">
            <Descriptions.Item label="Run ID" span={2}>{retrieval.run_id}</Descriptions.Item>
            <Descriptions.Item label="数据集">{retrieval.dataset_name || "--"}</Descriptions.Item>
            <Descriptions.Item label="完成时间">{formatDocumentDate(retrieval.completed_at)}</Descriptions.Item>
            <Descriptions.Item label={`Recall@${getRetrievalK(retrieval)}`}>{formatRate(getRetrievalMetric(retrieval, "recall"))}</Descriptions.Item>
            <Descriptions.Item label={`MRR@${getRetrievalK(retrieval)}`}>{getRetrievalMetric(retrieval, "mrr").toFixed(3)}</Descriptions.Item>
            <Descriptions.Item label="降级率">{formatRate(retrieval.summary.degraded_rate)}</Descriptions.Item>
            <Descriptions.Item label="问题数">{retrieval.summary.total_questions}</Descriptions.Item>
          </Descriptions>
          <pre className="json-viewer">{JSON.stringify(retrieval.items, null, 2)}</pre>
        </div>
      )}
    </Drawer>
  );
}
