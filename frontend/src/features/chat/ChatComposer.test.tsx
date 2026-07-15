import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ChatComposer } from "./ChatComposer";

describe("ChatComposer", () => {
  it("submits with Enter but keeps Shift+Enter for a newline", () => {
    const onSubmit = vi.fn();
    render(
      <ChatComposer
        value="优先排查哪个？"
        loading={false}
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const input = screen.getByLabelText("输入工业质量问题");
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter", shiftKey: false });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not submit while the workflow is running", () => {
    const onSubmit = vi.fn();
    render(
      <ChatComposer
        value="问题"
        loading
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.keyDown(screen.getByLabelText("输入工业质量问题"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
