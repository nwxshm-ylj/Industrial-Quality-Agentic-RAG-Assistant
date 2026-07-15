import {
  formatLatency,
  formatScore,
  getCitationScore,
  getIntent,
  shortenId,
} from "./presentation";

describe("chat presentation helpers", () => {
  it("formats millisecond and second latency", () => {
    expect(formatLatency(88.4)).toBe("88 ms");
    expect(formatLatency(1250)).toBe("1.25 s");
    expect(formatLatency(undefined)).toBe("--");
  });

  it("prefers the final rerank score for citations", () => {
    expect(getCitationScore({ score: 0.4, rerank_score: 0.91 })).toBe(0.91);
    expect(formatScore(0.91)).toBe("0.910");
  });

  it("reads intent from top-level response before metadata", () => {
    expect(getIntent({
      question: "q",
      answer: "a",
      citations: [],
      intent: "rule_query",
      metadata: { intent: "doc_qa" },
    })).toBe("rule_query");
  });

  it("shortens long request identifiers without losing both ends", () => {
    expect(shortenId("1234567890abcdefghij", 4)).toBe("1234…ghij");
  });
});
