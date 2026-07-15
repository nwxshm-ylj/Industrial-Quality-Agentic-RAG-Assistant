import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";

import { getApiErrorMessage } from "../api/client";
import { documentsApi, type UploadDocumentInput } from "../api/documents";
import type { DocumentInfo } from "../api/types";
import { can } from "../auth/rbac";
import { DocumentDetailDrawer } from "../features/knowledge-base/DocumentDetailDrawer";
import { DocumentStatusTag } from "../features/knowledge-base/DocumentStatusTag";
import { DocumentUploadPanel } from "../features/knowledge-base/DocumentUploadPanel";
import {
  formatDocumentDate,
  matchesDocument,
} from "../features/knowledge-base/presentation";
import { useAuthStore } from "../stores/authStore";

const statusOptions = [
  { label: "活动文档", value: "active" },
  { label: "索引完成", value: "indexed" },
  { label: "处理中", value: "uploaded" },
  { label: "索引失败", value: "failed" },
  { label: "已删除", value: "deleted" },
];

export function KnowledgeBasePage() {
  const { message, modal } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const role = useAuthStore((state) => state.user?.role);
  const canUpload = can(role, "knowledge:upload");
  const canAdmin = can(role, "knowledge:admin");
  const [statusFilter, setStatusFilter] = useState("active");
  const [search, setSearch] = useState("");
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const documentsQuery = useQuery({
    queryKey: ["documents", statusFilter],
    queryFn: () => documentsApi.list(statusFilter === "active" ? undefined : statusFilter),
  });

  const documents = useMemo(
    () => (documentsQuery.data?.documents || []).filter((document) => matchesDocument(document, search)),
    [documentsQuery.data?.documents, search],
  );

  const selectedFromList = documentsQuery.data?.documents.find(
    (document) => document.doc_id === selectedDocId,
  );
  const documentQuery = useQuery({
    queryKey: ["documents", "detail", selectedDocId],
    queryFn: () => documentsApi.get(selectedDocId as string),
    enabled: Boolean(selectedDocId),
  });

  const refreshDocuments = async () => {
    await queryClient.invalidateQueries({ queryKey: ["documents"] });
  };

  const uploadMutation = useMutation({
    mutationFn: (input: UploadDocumentInput) => documentsApi.upload(input),
    onSuccess: async (document) => {
      message.success(`文档已完成入库：${document.filename} · ${document.chunk_count} chunks`);
      setSelectedDocId(document.doc_id);
      await refreshDocuments();
    },
    onError: (error) => {
      message.error(`上传失败：${getApiErrorMessage(error)}`);
    },
    onSettled: () => {
      setUploadProgress(0);
    },
  });

  const reindexMutation = useMutation({
    mutationFn: (document: DocumentInfo) => documentsApi.reindex(document.doc_id),
    onSuccess: async (result) => {
      message.success(`${result.message} · ${result.chunk_count} chunks`);
      await refreshDocuments();
    },
    onError: (error) => {
      message.error(`重建失败：${getApiErrorMessage(error)}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (document: DocumentInfo) => documentsApi.remove(document.doc_id),
    onSuccess: async (result) => {
      message.success(result.message);
      setSelectedDocId(null);
      await refreshDocuments();
    },
    onError: (error) => {
      message.error(`删除失败：${getApiErrorMessage(error)}`);
    },
  });

  const handleUpload = async (file: File, docType: string, version: string) => {
    setUploadProgress(0);
    await uploadMutation.mutateAsync({
      file,
      docType,
      version,
      onProgress: setUploadProgress,
    });
  };

  const confirmReindex = (document: DocumentInfo) => {
    modal.confirm({
      title: "重建该文档的双索引？",
      content: (
        <div className="kb-confirm-copy">
          <p>{document.original_filename || document.filename}</p>
          <code>{document.doc_id}</code>
          <span>系统只会删除并重建该 doc_id 的 Qdrant 与 OpenSearch 数据。两路成功后才恢复 indexed。</span>
        </div>
      ),
      okText: "确认重建",
      cancelText: "取消",
      onOk: () => reindexMutation.mutateAsync(document),
    });
  };

  const confirmDelete = (document: DocumentInfo) => {
    modal.confirm({
      title: "删除该知识文档？",
      content: (
        <div className="kb-confirm-copy">
          <p>{document.original_filename || document.filename}</p>
          <code>{document.doc_id}</code>
          <span>该操作会按 doc_id 清理向量、关键词索引和 chunks，并将文档状态软删除。</span>
        </div>
      ),
      okText: "确认删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: () => deleteMutation.mutateAsync(document),
    });
  };

  const columns: TableColumnsType<DocumentInfo> = [
    {
      title: "文档",
      key: "document",
      width: 310,
      render: (_, document) => (
        <button className="document-name-cell" type="button" onClick={() => setSelectedDocId(document.doc_id)}>
          <span>{(document.file_ext || "DOC").replace(".", "").toUpperCase()}</span>
          <div>
            <strong>{document.original_filename || document.filename}</strong>
            <small>{document.doc_id}</small>
            {document.status === "failed" && <em>{document.failed_stage || "unknown stage"}</em>}
          </div>
        </button>
      ),
    },
    {
      title: "分类 / 版本",
      key: "type",
      width: 150,
      render: (_, document) => (
        <Space size={5} wrap>
          <Tag bordered={false}>{document.doc_type || "未分类"}</Tag>
          <span className="version-chip">{document.version}</span>
        </Space>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (status: string) => <DocumentStatusTag status={status} />,
    },
    {
      title: "Chunks",
      dataIndex: "chunk_count",
      width: 90,
      align: "right",
      render: (count: number) => <strong className="chunk-count">{count}</strong>,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 155,
      render: (value: string | null) => <span className="document-date">{formatDocumentDate(value)}</span>,
    },
    {
      title: "操作",
      key: "actions",
      width: canAdmin ? 210 : 90,
      fixed: "right",
      render: (_, document) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => setSelectedDocId(document.doc_id)}>详情</Button>
          {canAdmin && document.status !== "deleted" && (
            <>
              <Button type="link" size="small" loading={reindexMutation.isPending} onClick={() => confirmReindex(document)}>重建</Button>
              <Button type="link" danger size="small" loading={deleteMutation.isPending} onClick={() => confirmDelete(document)}>删除</Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  const sourceDocuments = documentsQuery.data?.documents || [];
  const indexedCount = sourceDocuments.filter((document) => document.status === "indexed").length;
  const failedCount = sourceDocuments.filter((document) => document.status === "failed").length;
  const totalChunks = sourceDocuments.reduce((sum, document) => sum + document.chunk_count, 0);
  const actionLoading = reindexMutation.isPending || deleteMutation.isPending;

  return (
    <div className="knowledge-base-page page-stack">
      <section className="kb-hero">
        <div>
          <Typography.Text className="page-eyebrow">KNOWLEDGE LIFECYCLE CONTROL</Typography.Text>
          <Typography.Title level={2}>企业知识库管理</Typography.Title>
          <Typography.Paragraph>
            管理工业文档元数据、版本与双索引生命周期。所有破坏性操作均由后端 RBAC 和审计日志继续强制保护。
          </Typography.Paragraph>
        </div>
        <div className="kb-hero__contract">
          <span><i className="is-online" />PostgreSQL</span>
          <b>→</b><span><i className="is-online" />Qdrant</span>
          <b>+</b><span><i className="is-online" />OpenSearch</span>
        </div>
      </section>

      <Row gutter={[14, 14]}>
        <Col xs={12} lg={6}><Card className="kb-metric-card"><Statistic title="当前文档" value={documentsQuery.data?.total || 0} suffix="docs" /></Card></Col>
        <Col xs={12} lg={6}><Card className="kb-metric-card"><Statistic title="索引完成" value={indexedCount} suffix="indexed" /></Card></Col>
        <Col xs={12} lg={6}><Card className="kb-metric-card"><Statistic title="Chunk 总量" value={totalChunks} suffix="chunks" /></Card></Col>
        <Col xs={12} lg={6}><Card className={`kb-metric-card${failedCount ? " kb-metric-card--warning" : ""}`}><Statistic title="失败待修复" value={failedCount} suffix="failed" /></Card></Col>
      </Row>

      <div className={`kb-workspace${canUpload ? "" : " kb-workspace--readonly"}`}>
        {canUpload && (
          <DocumentUploadPanel
            loading={uploadMutation.isPending}
            progress={uploadProgress}
            onUpload={handleUpload}
          />
        )}

        <section className="document-library">
          <div className="document-library__heading">
            <div>
              <Typography.Text className="panel-kicker">DOCUMENT REGISTRY</Typography.Text>
              <Typography.Title level={4}>文档资产</Typography.Title>
            </div>
            <Space>
              {!canUpload && <Tag bordered={false}>只读模式</Tag>}
              <Button loading={documentsQuery.isFetching} onClick={() => documentsQuery.refetch()}>刷新</Button>
            </Space>
          </div>

          <div className="document-toolbar">
            <Input.Search
              allowClear
              placeholder="搜索文件名、doc_id、类型或版本"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Select value={statusFilter} options={statusOptions} onChange={setStatusFilter} />
          </div>

          <Table<DocumentInfo>
            className="document-table"
            rowKey="doc_id"
            columns={columns}
            dataSource={documents}
            loading={documentsQuery.isLoading}
            scroll={{ x: 1030 }}
            pagination={{ pageSize: 8, showSizeChanger: false, showTotal: (total) => `共 ${total} 个文档` }}
            locale={{ emptyText: documentsQuery.isError ? `加载失败：${getApiErrorMessage(documentsQuery.error)}` : "当前筛选条件下没有文档" }}
          />
        </section>
      </div>

      <DocumentDetailDrawer
        open={Boolean(selectedDocId)}
        loading={documentQuery.isLoading}
        document={documentQuery.data || selectedFromList}
        canAdmin={canAdmin}
        actionLoading={actionLoading}
        onClose={() => setSelectedDocId(null)}
        onReindex={confirmReindex}
        onDelete={confirmDelete}
      />
    </div>
  );
}
