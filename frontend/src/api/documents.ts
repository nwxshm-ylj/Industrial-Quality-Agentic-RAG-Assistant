import type { AxiosProgressEvent } from "axios";

import { apiClient } from "./client";
import type {
  DocumentDeleteResponse,
  DocumentInfo,
  DocumentListResponse,
  DocumentReindexResponse,
  DocumentUploadResponse,
} from "./types";

const DOCUMENT_OPERATION_TIMEOUT_MS = 300_000;

export interface UploadDocumentInput {
  file: File;
  docType?: string;
  version: string;
  onProgress?: (percent: number) => void;
}

export const documentsApi = {
  async list(status?: string): Promise<DocumentListResponse> {
    const response = await apiClient.get<DocumentListResponse>("/documents", {
      params: status ? { status } : undefined,
    });
    return response.data;
  },

  async get(docId: string): Promise<DocumentInfo> {
    const response = await apiClient.get<DocumentInfo>(
      `/documents/${encodeURIComponent(docId)}`,
    );
    return response.data;
  },

  async upload(input: UploadDocumentInput): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", input.file, input.file.name);
    if (input.docType?.trim()) {
      formData.append("doc_type", input.docType.trim());
    }
    formData.append("version", input.version.trim() || "v1");

    const response = await apiClient.post<DocumentUploadResponse>(
      "/documents/upload",
      formData,
      {
        timeout: DOCUMENT_OPERATION_TIMEOUT_MS,
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event: AxiosProgressEvent) => {
          if (event.total && input.onProgress) {
            input.onProgress(Math.round((event.loaded / event.total) * 100));
          }
        },
      },
    );
    return response.data;
  },

  async remove(docId: string): Promise<DocumentDeleteResponse> {
    const response = await apiClient.delete<DocumentDeleteResponse>(
      `/documents/${encodeURIComponent(docId)}`,
      { timeout: DOCUMENT_OPERATION_TIMEOUT_MS },
    );
    return response.data;
  },

  async reindex(docId: string): Promise<DocumentReindexResponse> {
    const response = await apiClient.post<DocumentReindexResponse>(
      `/documents/${encodeURIComponent(docId)}/reindex`,
      undefined,
      { timeout: DOCUMENT_OPERATION_TIMEOUT_MS },
    );
    return response.data;
  },
};
