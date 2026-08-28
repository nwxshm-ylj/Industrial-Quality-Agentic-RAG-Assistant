import { describe, expect, it } from "vitest";

import { normalizeAnswerMarkdown } from "./markdown";

describe("normalizeAnswerMarkdown", () => {
  it("converts common HTML br variants into Markdown hard breaks", () => {
    expect(normalizeAnswerMarkdown("CO<br>HC<br/>NOx<BR />O2")).toBe(
      "CO  \nHC  \nNOx  \nO2",
    );
  });

  it("does not enable or rewrite other raw HTML", () => {
    const answer = "结果：<script>alert('xss')</script>";
    expect(normalizeAnswerMarkdown(answer)).toBe(answer);
  });
});
