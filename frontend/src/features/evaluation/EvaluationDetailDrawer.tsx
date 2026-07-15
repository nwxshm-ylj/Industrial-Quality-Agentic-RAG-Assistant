import { Descriptions, Drawer, Empty, Table, Tag, Typography, type TableColumnsType } from "antd";

import type { EvalItemInfo, EvalRunResponse, RetrievalEvalRunResponse } from "../../api/types";
import { formatDocumentDate } from "../knowledge-base/presentation";
import { formatRate, getRetrievalK, getRetrievalMetric } from "./presentation";

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
          </Descriptions>
          {generation.items?.length ? (
            <Table rowKey="id" columns={itemColumns} dataSource={generation.items} scroll={{ x: 780 }} pagination={{ pageSize: 8 }} />
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
