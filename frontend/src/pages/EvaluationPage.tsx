import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Col,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";

import { getApiErrorMessage } from "../api/client";
import { evaluationApi } from "../api/evaluation";
import { feedbackApi } from "../api/feedback";
import type {
  EvalRunInfo,
  FeedbackItem,
  FeedbackRating,
  RetrievalEvalRunInfo,
} from "../api/types";
import { EvaluationDetailDrawer } from "../features/evaluation/EvaluationDetailDrawer";
import {
  formatMetric,
  formatRate,
  getRetrievalK,
  getRetrievalLatency,
  getRetrievalMetric,
} from "../features/evaluation/presentation";
import { formatDocumentDate } from "../features/knowledge-base/presentation";

type SelectedRun = { kind: "generation" | "retrieval"; runId: string } | null;

const ratingLabels: Record<string, { label: string; color: string }> = {
  positive: { label: "正向", color: "success" },
  neutral: { label: "中性", color: "default" },
  negative: { label: "负向", color: "error" },
};

export function EvaluationPage() {
  const { message, modal } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const [ratingFilter, setRatingFilter] = useState<FeedbackRating | "all">("all");
  const [retrievalTopK, setRetrievalTopK] = useState(5);
  const [selectedRun, setSelectedRun] = useState<SelectedRun>(null);

  const feedbackStats = useQuery({ queryKey: ["feedback", "stats"], queryFn: feedbackApi.stats });
  const feedbackList = useQuery({
    queryKey: ["feedback", "list", ratingFilter],
    queryFn: () => feedbackApi.list({
      rating: ratingFilter === "all" ? undefined : ratingFilter,
      limit: 100,
    }),
  });
  const generationRuns = useQuery({
    queryKey: ["evaluation", "generation", "runs"],
    queryFn: () => evaluationApi.listRuns(50),
  });
  const retrievalRuns = useQuery({
    queryKey: ["evaluation", "retrieval", "runs"],
    queryFn: () => evaluationApi.listRetrievalRuns(50),
    retry: false,
  });
  const generationDetail = useQuery({
    queryKey: ["evaluation", "generation", "detail", selectedRun?.runId],
    queryFn: () => evaluationApi.getRun(selectedRun?.runId as string),
    enabled: selectedRun?.kind === "generation",
  });
  const retrievalDetail = useQuery({
    queryKey: ["evaluation", "retrieval", "detail", selectedRun?.runId],
    queryFn: () => evaluationApi.getRetrievalRun(selectedRun?.runId as string),
    enabled: selectedRun?.kind === "retrieval",
    retry: false,
  });

  const generationMutation = useMutation({
    mutationFn: evaluationApi.run,
    onSuccess: async (run) => {
      message.success(`评估完成：${run.run_id}`);
      await queryClient.invalidateQueries({ queryKey: ["evaluation", "generation"] });
    },
    onError: (error) => message.error(`评估失败：${getApiErrorMessage(error)}`),
  });
  const retrievalMutation = useMutation({
    mutationFn: () => evaluationApi.runRetrieval({
      top_k: retrievalTopK,
      k_values: Array.from(new Set([1, 3, 5, retrievalTopK])).sort((a, b) => a - b),
    }),
    onSuccess: async (run) => {
      message.success(`检索评估完成：${run.run_id}`);
      await queryClient.invalidateQueries({ queryKey: ["evaluation", "retrieval"] });
    },
    onError: (error) => message.error(`检索评估失败：${getApiErrorMessage(error)}`),
  });

  const confirmGenerationRun = () => {
    modal.confirm({
      title: "运行生成式 RAG 评估？",
      content: "该任务会读取评估集并调用真实 LangGraph/LLM，可能持续数分钟并产生模型用量。",
      okText: "确认运行",
      cancelText: "取消",
      onOk: () => generationMutation.mutateAsync(),
    });
  };
  const confirmRetrievalRun = () => {
    modal.confirm({
      title: "运行独立检索评估？",
      content: `将以 Top K=${retrievalTopK} 运行 Qdrant + OpenSearch 检索评估。不会生成最终回答，但可能调用 Query Embedding API。`,
      okText: "确认运行",
      cancelText: "取消",
      onOk: () => retrievalMutation.mutateAsync(),
    });
  };

  const feedbackColumns: TableColumnsType<FeedbackItem> = [
    { title: "时间", dataIndex: "created_at", width: 145, render: formatDocumentDate },
    { title: "用户", dataIndex: "username", width: 95 },
    { title: "反馈", dataIndex: "rating", width: 85, render: (rating: string) => <Tag color={ratingLabels[rating]?.color} bordered={false}>{ratingLabels[rating]?.label || rating}</Tag> },
    { title: "意图", dataIndex: "intent", width: 105 },
    { title: "问题", dataIndex: "question", ellipsis: true, width: 250 },
    { title: "备注", dataIndex: "comment", ellipsis: true, width: 220, render: (value) => value || "--" },
  ];
  const generationColumns: TableColumnsType<EvalRunInfo> = [
    { title: "运行", dataIndex: "run_id", width: 190, ellipsis: true },
    { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag bordered={false}>{value}</Tag> },
    { title: "问题", dataIndex: "total_questions", width: 75 },
    { title: "Intent", dataIndex: "intent_accuracy", width: 90, render: formatRate },
    { title: "Source", dataIndex: "source_hit_rate", width: 90, render: formatRate },
    { title: "Keyword", dataIndex: "answer_keyword_hit_rate", width: 90, render: formatRate },
    { title: "Memory", dataIndex: "memory_followup_success_rate", width: 90, render: formatRate },
    { title: "Avg latency", dataIndex: "avg_latency_ms", width: 105, render: (value) => `${Number(value || 0).toFixed(0)} ms` },
    { title: "详情", key: "details", width: 70, fixed: "right", render: (_, run) => <Button type="link" size="small" onClick={() => setSelectedRun({ kind: "generation", runId: run.run_id })}>查看</Button> },
  ];
  const retrievalColumns: TableColumnsType<RetrievalEvalRunInfo> = [
    { title: "运行", dataIndex: "run_id", width: 190, ellipsis: true },
    { title: "数据集", dataIndex: "dataset_name", width: 120, render: (value) => value || "--" },
    { title: "问题", key: "questions", width: 75, render: (_, run) => run.summary.total_questions },
    { title: "Recall", key: "recall", width: 90, render: (_, run) => formatRate(getRetrievalMetric(run, "recall")) },
    { title: "MRR", key: "mrr", width: 85, render: (_, run) => formatMetric(getRetrievalMetric(run, "mrr")) },
    { title: "nDCG", key: "ndcg", width: 85, render: (_, run) => formatMetric(getRetrievalMetric(run, "ndcg")) },
    { title: "P95", key: "p95", width: 85, render: (_, run) => `${getRetrievalLatency(run, "p95").toFixed(0)} ms` },
    { title: "降级率", key: "degraded", width: 90, render: (_, run) => formatRate(run.summary.degraded_rate) },
    { title: "详情", key: "details", width: 70, fixed: "right", render: (_, run) => <Button type="link" size="small" onClick={() => setSelectedRun({ kind: "retrieval", runId: run.run_id })}>查看</Button> },
  ];

  const stats = feedbackStats.data;
  const latestGeneration = generationRuns.data?.runs[0];
  const latestRetrieval = retrievalRuns.data?.runs[0];

  const qualityTab = (
    <div className="evaluation-tab-stack">
      <Row gutter={[14, 14]}>
        <Col xs={12} xl={6}><Card className="quality-metric"><Statistic title="反馈总量" value={stats?.total || 0} /></Card></Col>
        <Col xs={12} xl={6}><Card className="quality-metric quality-metric--positive"><Statistic title="正向率" value={(stats?.positive_rate || 0) * 100} precision={1} suffix="%" /></Card></Col>
        <Col xs={12} xl={6}><Card className="quality-metric quality-metric--negative"><Statistic title="负向率" value={(stats?.negative_rate || 0) * 100} precision={1} suffix="%" /></Card></Col>
        <Col xs={12} xl={6}><Card className="quality-metric"><Statistic title="最新评估问题" value={latestGeneration?.total_questions || 0} /></Card></Col>
      </Row>

      <div className="evaluation-grid">
        <Card className="feedback-distribution" bordered={false}>
          <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">USER SIGNALS</Typography.Text><Typography.Title level={4}>反馈分布</Typography.Title></div><Tag bordered={false}>CLOSED LOOP</Tag></div>
          <div className="feedback-bars">
            <div><span>正向</span><Progress percent={(stats?.positive_rate || 0) * 100} strokeColor="#1b7f5c" showInfo={false} /><b>{stats?.positive_count || 0}</b></div>
            <div><span>中性</span><Progress percent={stats?.total ? ((stats.neutral_count / stats.total) * 100) : 0} strokeColor="#71818c" showInfo={false} /><b>{stats?.neutral_count || 0}</b></div>
            <div><span>负向</span><Progress percent={(stats?.negative_rate || 0) * 100} strokeColor="#b64040" showInfo={false} /><b>{stats?.negative_count || 0}</b></div>
          </div>
          <div className="intent-signal-list">
            {Object.entries(stats?.by_intent || {}).map(([intent, count]) => <span key={intent}><b>{intent}</b><em>{count}</em></span>)}
          </div>
        </Card>

        <Card className="latest-evaluation" bordered={false}>
          <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">LATEST GENERATION RUN</Typography.Text><Typography.Title level={4}>生成质量指标</Typography.Title></div><Button type="primary" loading={generationMutation.isPending} onClick={confirmGenerationRun}>运行评估</Button></div>
          {latestGeneration ? (
            <div className="latest-evaluation__metrics">
              <span><b>{formatRate(latestGeneration.intent_accuracy)}</b><small>Intent accuracy</small></span>
              <span><b>{formatRate(latestGeneration.source_hit_rate)}</b><small>Source hit</small></span>
              <span><b>{formatRate(latestGeneration.answer_keyword_hit_rate)}</b><small>Keyword hit</small></span>
              <span><b>{formatRate(latestGeneration.memory_followup_success_rate)}</b><small>Memory follow-up</small></span>
            </div>
          ) : <Alert type="info" showIcon message="尚无生成式评估记录" />}
        </Card>
      </div>

      <Card className="evaluation-table-card" bordered={false}>
        <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">RECENT FEEDBACK</Typography.Text><Typography.Title level={4}>最近用户反馈</Typography.Title></div><Select value={ratingFilter} onChange={setRatingFilter} options={[{ label: "全部", value: "all" }, { label: "正向", value: "positive" }, { label: "中性", value: "neutral" }, { label: "负向", value: "negative" }]} /></div>
        <Table rowKey="id" columns={feedbackColumns} dataSource={feedbackList.data || []} loading={feedbackList.isLoading} scroll={{ x: 900 }} pagination={{ pageSize: 6 }} />
      </Card>

      <Card className="evaluation-table-card" bordered={false}>
        <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">GENERATION RUNS</Typography.Text><Typography.Title level={4}>生成式评估历史</Typography.Title></div><Button onClick={() => generationRuns.refetch()}>刷新</Button></div>
        <Table rowKey="run_id" columns={generationColumns} dataSource={generationRuns.data?.runs || []} loading={generationRuns.isLoading} scroll={{ x: 1050 }} pagination={{ pageSize: 6 }} />
      </Card>
    </div>
  );

  const retrievalTab = (
    <div className="evaluation-tab-stack">
      {retrievalRuns.isError && <Alert type="warning" showIcon message="独立检索评估接口暂不可用" description={`${getApiErrorMessage(retrievalRuns.error)}。请重新构建当前源码的 API 镜像。`} />}
      <Card className="retrieval-runner" bordered={false}>
        <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">RETRIEVAL BENCHMARK</Typography.Text><Typography.Title level={4}>Qdrant + OpenSearch 检索评估</Typography.Title></div><Space><Select value={retrievalTopK} onChange={setRetrievalTopK} options={[5, 10, 20].map((value) => ({ label: `Top K ${value}`, value }))} /><Button type="primary" loading={retrievalMutation.isPending} onClick={confirmRetrievalRun}>运行检索评估</Button></Space></div>
        <Typography.Paragraph>独立计算 Recall、MRR、HitRate、nDCG 与检索延迟，不调用最终答案生成 LLM。</Typography.Paragraph>
        {latestRetrieval && (
          <div className="retrieval-metric-grid">
            <span><b>{formatRate(getRetrievalMetric(latestRetrieval, "recall"))}</b><small>Recall@{getRetrievalK(latestRetrieval)}</small></span>
            <span><b>{formatMetric(getRetrievalMetric(latestRetrieval, "mrr"))}</b><small>MRR@{getRetrievalK(latestRetrieval)}</small></span>
            <span><b>{formatMetric(getRetrievalMetric(latestRetrieval, "ndcg"))}</b><small>nDCG@{getRetrievalK(latestRetrieval)}</small></span>
            <span><b>{getRetrievalLatency(latestRetrieval, "p95").toFixed(0)} ms</b><small>Retrieval P95</small></span>
            <span><b>{formatRate(latestRetrieval.summary.degraded_rate)}</b><small>Degraded rate</small></span>
          </div>
        )}
      </Card>
      <Card className="evaluation-table-card" bordered={false}>
        <div className="eval-card-heading"><div><Typography.Text className="panel-kicker">RETRIEVAL RUNS</Typography.Text><Typography.Title level={4}>检索评估历史</Typography.Title></div><Button onClick={() => retrievalRuns.refetch()}>刷新</Button></div>
        <Table rowKey="run_id" columns={retrievalColumns} dataSource={retrievalRuns.data?.runs || []} loading={retrievalRuns.isLoading} scroll={{ x: 950 }} pagination={{ pageSize: 8 }} />
      </Card>
    </div>
  );

  return (
    <div className="evaluation-page page-stack">
      <section className="evaluation-hero">
        <div><Typography.Text className="page-eyebrow">QUALITY IMPROVEMENT LOOP</Typography.Text><Typography.Title level={2}>RAG Evaluation Dashboard</Typography.Title><Typography.Paragraph>连接用户反馈、生成质量、检索召回和延迟指标，让每一次模型改动都有可比较的质量证据。</Typography.Paragraph></div>
        <div className="quality-loop"><span>QUESTION</span><b>→</b><span>ANSWER</span><b>→</b><span>FEEDBACK</span><b>→</b><span>EVALUATE</span></div>
      </section>
      <Tabs className="evaluation-tabs" items={[{ key: "quality", label: "反馈与生成质量", children: qualityTab }, { key: "retrieval", label: "独立检索评估", children: retrievalTab }]} />
      <EvaluationDetailDrawer
        open={Boolean(selectedRun)}
        kind={selectedRun?.kind || null}
        loading={generationDetail.isLoading || retrievalDetail.isLoading}
        generation={generationDetail.data}
        retrieval={retrievalDetail.data}
        onClose={() => setSelectedRun(null)}
      />
    </div>
  );
}
