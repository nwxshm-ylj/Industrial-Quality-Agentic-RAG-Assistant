import { formatDocumentDate, getDocumentStatus, matchesDocument } from "./presentation";

const document = {
  doc_id: "doc-quality-01",
  filename: "wheel-hub-sop.md",
  original_filename: "轮毂检查规范.md",
  doc_type: "SOP",
  file_ext: ".md",
  version: "v3",
  status: "indexed",
  chunk_count: 12,
};

describe("knowledge-base presentation", () => {
  it("describes indexed only after both retrieval indexes succeed", () => {
    expect(getDocumentStatus("indexed").description).toContain("Qdrant");
    expect(getDocumentStatus("indexed").description).toContain("OpenSearch");
    expect(getDocumentStatus("failed").label).toBe("索引失败");
  });

  it("searches metadata fields case-insensitively", () => {
    expect(matchesDocument(document, "sop")).toBe(true);
    expect(matchesDocument(document, "轮毂")).toBe(true);
    expect(matchesDocument(document, "v3")).toBe(true);
    expect(matchesDocument(document, "FMEA")).toBe(false);
  });

  it("keeps invalid dates readable", () => {
    expect(formatDocumentDate("not-a-date")).toBe("not-a-date");
    expect(formatDocumentDate(null)).toBe("--");
  });
});
