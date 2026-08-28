/**
 * Keep model output as Markdown while accepting the common HTML line-break
 * variants returned by some prompts/models. Raw HTML stays disabled in
 * ReactMarkdown so model output cannot inject arbitrary HTML.
 */
export function normalizeAnswerMarkdown(value: string): string {
  return value.replace(/\s*<br\s*\/?>\s*/gi, "  \n");
}
