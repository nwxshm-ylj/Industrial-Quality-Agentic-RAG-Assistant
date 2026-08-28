import { App as AntdApp, Alert, Button, Drawer, Empty, Space, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";

import { observabilityApi } from "../../api/observability";
import type {
  ChatProgressEvent,
  ChatResponse,
  RequestDiagnosticSnapshot,
} from "../../api/types";
import { DiagnosticSnapshotView } from "./DiagnosticSnapshotView";
import { buildLocalDiagnosticSnapshot } from "./diagnostics";

interface AnswerDiagnosisDrawerProps {
  open: boolean;
  question?: string;
  response?: ChatResponse;
  progressEvents?: ChatProgressEvent[];
  canLoadHistorical: boolean;
  onClose: () => void;
}

function mergeSnapshots(
  local: RequestDiagnosticSnapshot,
  server?: RequestDiagnosticSnapshot | null,
): RequestDiagnosticSnapshot {
  if (!server) {
    return local;
  }
  const localChecksByCode = new Map(local.checks.map((item) => [item.code, item]));
  const checks = server.checks.map((item) => localChecksByCode.get(item.code) || item);
  for (const item of local.checks) {
    if (!checks.some((existing) => existing.code === item.code)) {
      checks.push(item);
    }
  }
  const localContexts = local.generation.contexts;
  const hydratedGenerationContexts = server.generation.contexts.length
    ? server.generation.contexts.map((serverContext) => {
      const matchingLocal = localContexts.find((localContext) => (
        (serverContext.chunk_id && localContext.chunk_id === serverContext.chunk_id)
        || (serverContext.evidence_bundle_id
          && localContext.evidence_bundle_id === serverContext.evidence_bundle_id)
      ));
      return matchingLocal
        ? { ...serverContext, text_excerpt: matchingLocal.text_excerpt }
        : serverContext;
    })
    : localContexts;
  return {
    ...server,
    content_capture_enabled: true,
    routing: { ...server.routing, ...local.routing },
    generation: {
      ...server.generation,
      contexts: hydratedGenerationContexts,
      citations: local.generation.citations,
      answer_excerpt: local.generation.answer_excerpt,
    },
    workflow_events: local.workflow_events?.length
      ? local.workflow_events
      : server.workflow_events,
    checks,
  };
}

export function AnswerDiagnosisDrawer({
  open,
  question,
  response,
  progressEvents = [],
  canLoadHistorical,
  onClose,
}: AnswerDiagnosisDrawerProps) {
  const { message } = AntdApp.useApp();
  const requestId = response?.request_id || "";
  const serverDiagnostics = useQuery({
    queryKey: ["diagnostics", "request", requestId],
    queryFn: () => observabilityApi.requestDiagnostics(requestId),
    enabled: open && canLoadHistorical && Boolean(requestId),
    retry: false,
  });

  const localSnapshot = response ? buildLocalDiagnosticSnapshot(response) : null;
  if (localSnapshot && progressEvents.length) {
    localSnapshot.workflow_events = progressEvents;
  }
  const snapshot = localSnapshot
    ? mergeSnapshots(localSnapshot, serverDiagnostics.data?.snapshot)
    : serverDiagnostics.data?.snapshot;
  const exportPayload = snapshot ? {
    request_id: requestId,
    question,
    progress_events: progressEvents,
    diagnosis: snapshot,
    limitations: serverDiagnostics.data?.limitations || [],
  } : null;

  const copyRequestId = async () => {
    try {
      await navigator.clipboard.writeText(requestId);
      message.success("request_id 已复制");
    } catch {
      message.warning("浏览器未授权剪贴板访问");
    }
  };

  const exportDiagnosis = () => {
    if (!exportPayload) return;
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `answer-diagnosis-${requestId || "local"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Drawer
      width={860}
      open={open}
      onClose={onClose}
      title={(
        <div>
          <Typography.Text className="panel-kicker">ANSWER DIAGNOSTICS</Typography.Text>
          <Typography.Title level={4}>回答链路诊断</Typography.Title>
        </div>
      )}
      extra={(
        <Space>
          <Button size="small" onClick={copyRequestId} disabled={!requestId}>复制 RID</Button>
          <Button size="small" onClick={exportDiagnosis} disabled={!exportPayload}>导出 JSON</Button>
        </Space>
      )}
    >
      {!canLoadHistorical && (
        <Alert
          type="info"
          showIcon
          message="当前按只读用户权限展示本轮响应证据，不查询内部历史诊断快照。"
        />
      )}
      {serverDiagnostics.isError && localSnapshot && (
        <Alert
          type="warning"
          showIcon
          message="历史诊断快照暂不可用，当前仍可使用本轮响应完成证据对比。"
        />
      )}
      {snapshot ? (
        <DiagnosticSnapshotView
          snapshot={snapshot}
          aiEvents={serverDiagnostics.data?.ai_events}
          retrievalEvents={serverDiagnostics.data?.retrieval_events}
          limitations={serverDiagnostics.data?.limitations}
        />
      ) : (
        <Empty description="当前没有可诊断的回答" />
      )}
    </Drawer>
  );
}
