import type { DocumentInfo } from "../../api/types";

export type DocumentStatus = "uploaded" | "indexed" | "deleted" | "failed" | string;

interface StatusPresentation {
  label: string;
  color: string;
  description: string;
}

const statusPresentations: Record<string, StatusPresentation> = {
  indexed: {
    label: "索引完成",
    color: "success",
    description: "PostgreSQL 元数据、Qdrant 向量和 OpenSearch 关键词索引均已完成。",
  },
  uploaded: {
    label: "处理中",
    color: "processing",
    description: "文档已上传，但尚未完成全部检索索引。",
  },
  failed: {
    label: "索引失败",
    color: "error",
    description: "生命周期部分阶段失败，可修复外部依赖后重新执行索引。",
  },
  deleted: {
    label: "已删除",
    color: "default",
    description: "文档已软删除，活动检索索引中不应再包含该 doc_id。",
  },
};

export function getDocumentStatus(status: DocumentStatus): StatusPresentation {
  return statusPresentations[status] || {
    label: status || "未知",
    color: "default",
    description: "后端返回了未识别的文档状态，请检查服务版本。",
  };
}

export function formatDocumentDate(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function matchesDocument(document: DocumentInfo, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    document.filename,
    document.original_filename,
    document.doc_id,
    document.doc_type,
    document.version,
  ].some((value) => String(value || "").toLowerCase().includes(normalized));
}
