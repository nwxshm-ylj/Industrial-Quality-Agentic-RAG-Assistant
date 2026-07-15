import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd";

import type { DocumentInfo } from "../../api/types";
import { DocumentStatusTag } from "./DocumentStatusTag";
import { formatDocumentDate, getDocumentStatus } from "./presentation";

interface DocumentDetailDrawerProps {
  open: boolean;
  loading: boolean;
  document?: DocumentInfo;
  canAdmin: boolean;
  actionLoading: boolean;
  onClose: () => void;
  onReindex: (document: DocumentInfo) => void;
  onDelete: (document: DocumentInfo) => void;
}

function IndexContract({ document }: { document: DocumentInfo }) {
  const indexed = document.status === "indexed";
  const deleted = document.status === "deleted";
  const state = indexed ? "ACTIVE" : deleted ? "CLEARED" : "NOT ACTIVE";

  return (
    <div className="index-contract-grid">
      <div><i className="is-online" /><span><b>PostgreSQL</b><small>metadata / chunks</small></span><strong>RECORDED</strong></div>
      <div><i className={indexed ? "is-online" : "is-offline"} /><span><b>Qdrant</b><small>vector index</small></span><strong>{state}</strong></div>
      <div><i className={indexed ? "is-online" : "is-offline"} /><span><b>OpenSearch</b><small>keyword index</small></span><strong>{state}</strong></div>
    </div>
  );
}

export function DocumentDetailDrawer({
  open,
  loading,
  document,
  canAdmin,
  actionLoading,
  onClose,
  onReindex,
  onDelete,
}: DocumentDetailDrawerProps) {
  return (
    <Drawer
      className="document-drawer"
      width={520}
      open={open}
      onClose={onClose}
      title={(
        <div>
          <Typography.Text className="panel-kicker">DOCUMENT METADATA</Typography.Text>
          <Typography.Title level={4}>文档详情</Typography.Title>
        </div>
      )}
      extra={document ? <DocumentStatusTag status={document.status} /> : null}
      footer={document && canAdmin && document.status !== "deleted" ? (
        <Space>
          <Button loading={actionLoading} onClick={() => onReindex(document)}>重建双索引</Button>
          <Button danger loading={actionLoading} onClick={() => onDelete(document)}>删除文档</Button>
        </Space>
      ) : null}
    >
      {loading && <Skeleton active paragraph={{ rows: 8 }} />}

      {!loading && document && (
        <div className="document-detail">
          <div className="document-detail__hero">
            <span>{(document.file_ext || "DOC").replace(".", "").toUpperCase()}</span>
            <div>
              <Typography.Title level={4}>{document.original_filename || document.filename}</Typography.Title>
              <Typography.Text>{document.doc_id}</Typography.Text>
            </div>
          </div>

          {document.status === "failed" && (
            <Alert
              type="error"
              showIcon
              message={`索引失败阶段：${document.failed_stage || "unknown"}`}
              description={document.error_message || "后端未返回错误详情，请检查结构化日志。"}
            />
          )}

          <Typography.Text className="panel-kicker">INDEX CONSISTENCY</Typography.Text>
          <IndexContract document={document} />
          <p className="index-contract-copy">{getDocumentStatus(document.status).description}</p>

          <Descriptions column={1} colon={false} className="document-descriptions">
            <Descriptions.Item label="安全文件名">{document.filename}</Descriptions.Item>
            <Descriptions.Item label="文档类型"><Tag bordered={false}>{document.doc_type || "未分类"}</Tag></Descriptions.Item>
            <Descriptions.Item label="扩展名">{document.file_ext || "--"}</Descriptions.Item>
            <Descriptions.Item label="版本">{document.version}</Descriptions.Item>
            <Descriptions.Item label="Chunk 数量">{document.chunk_count}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{formatDocumentDate(document.created_at)}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{formatDocumentDate(document.updated_at)}</Descriptions.Item>
          </Descriptions>
        </div>
      )}
    </Drawer>
  );
}
