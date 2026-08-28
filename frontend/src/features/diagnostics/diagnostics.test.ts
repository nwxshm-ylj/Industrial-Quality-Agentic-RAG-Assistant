import type { ChatResponse } from "../../api/types";
import { buildLocalDiagnosticSnapshot } from "./diagnostics";

describe("answer diagnostics", () => {
  it("flags a possible empty-field conflict without an LLM", () => {
    const response = {
      question: "有没有无锡万华的缺陷案例？",
      answer: "资料中措施栏为空。",
      citations: [{ chunk_id: "chunk-1", evidence_chunk_ids: ["chunk-1", "chunk-2"] }],
      contexts: [{
        chunk_id: "chunk-1",
        text: "措施：更换冲头和凹模套",
        evidence_chunk_count: 2,
        evidence_chunk_ids: ["chunk-1", "chunk-2"],
      }],
      request_id: "request-1",
      session_id: "session-1",
    } as ChatResponse;

    const snapshot = buildLocalDiagnosticSnapshot(response);
    expect(snapshot.checks.some((item) => item.code === "possible_empty_field_conflict")).toBe(true);
  });

  it("flags missing citation mappings", () => {
    const response = {
      question: "有没有历史案例？",
      answer: "已找到资料。",
      citations: [],
      contexts: [{ chunk_id: "chunk-1", text: "措施：更换模具" }],
      request_id: "request-2",
      session_id: "session-2",
    } as ChatResponse;

    const snapshot = buildLocalDiagnosticSnapshot(response);
    expect(snapshot.checks.some((item) => item.code === "citation_missing")).toBe(true);
  });
});
