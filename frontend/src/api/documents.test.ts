import { vi } from "vitest";

import { apiClient } from "./client";
import { documentsApi } from "./documents";

describe("documentsApi", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists documents with the backend status query", async () => {
    const payload = { documents: [], total: 0 };
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: payload });

    await expect(documentsApi.list("failed")).resolves.toEqual(payload);
    expect(get).toHaveBeenCalledWith("/documents", { params: { status: "failed" } });
  });

  it("builds multipart upload data without changing the API contract", async () => {
    const payload = {
      doc_id: "doc-1",
      filename: "quality.txt",
      version: "v2",
      status: "indexed",
      chunk_count: 3,
    };
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: payload });
    const file = new File(["quality"], "quality.txt", { type: "text/plain" });

    await expect(documentsApi.upload({
      file,
      docType: "SOP",
      version: "v2",
    })).resolves.toEqual(payload);

    const [path, formData, config] = post.mock.calls[0];
    expect(path).toBe("/documents/upload");
    expect(formData).toBeInstanceOf(FormData);
    expect((formData as FormData).get("doc_type")).toBe("SOP");
    expect((formData as FormData).get("version")).toBe("v2");
    expect(config).toMatchObject({ timeout: 300_000 });
  });

  it("keeps destructive operations scoped to the encoded doc_id", async () => {
    const remove = vi.spyOn(apiClient, "delete").mockResolvedValue({
      data: { doc_id: "doc / 1", status: "deleted", message: "ok" },
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      data: { doc_id: "doc / 1", status: "indexed", chunk_count: 2, message: "ok" },
    });

    await documentsApi.remove("doc / 1");
    await documentsApi.reindex("doc / 1");

    expect(remove).toHaveBeenCalledWith(
      "/documents/doc%20%2F%201",
      { timeout: 300_000 },
    );
    expect(post).toHaveBeenCalledWith(
      "/documents/doc%20%2F%201/reindex",
      undefined,
      { timeout: 300_000 },
    );
  });
});
