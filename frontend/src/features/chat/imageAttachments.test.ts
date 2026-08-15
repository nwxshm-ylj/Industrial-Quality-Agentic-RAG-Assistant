import { appendImageAttachments } from "./imageAttachments";


describe("image attachments", () => {
  it("converts a supported image to a data URI", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "defect.png", {
      type: "image/png",
    });

    const result = await appendImageAttachments([], [file]);

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      name: "defect.png",
      type: "image/png",
      size: 3,
    });
    expect(result[0].dataUrl).toMatch(/^data:image\/png;base64,/);
  });

  it("rejects unsupported files and more than five images", async () => {
    const textFile = new File(["not-an-image"], "note.txt", {
      type: "text/plain",
    });
    await expect(appendImageAttachments([], [textFile])).rejects.toThrow(
      "仅支持 JPG、PNG、WebP",
    );

    const images = Array.from({ length: 6 }, (_, index) => new File(
      [new Uint8Array([index])],
      `image-${index}.png`,
      { type: "image/png" },
    ));
    await expect(appendImageAttachments([], images)).rejects.toThrow(
      "最多上传 5 张图片",
    );
  });
});
