export const MAX_CHAT_IMAGES = 5;
export const MAX_CHAT_IMAGE_BYTES = 8 * 1024 * 1024;
export const MAX_CHAT_IMAGE_TOTAL_BYTES = 20 * 1024 * 1024;

const SUPPORTED_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

export interface ChatImageAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  dataUrl: string;
}

export async function appendImageAttachments(
  current: ChatImageAttachment[],
  files: File[],
): Promise<ChatImageAttachment[]> {
  if (!files.length) {
    return current;
  }
  if (current.length + files.length > MAX_CHAT_IMAGES) {
    throw new Error(`每次问答最多上传 ${MAX_CHAT_IMAGES} 张图片`);
  }

  const currentBytes = current.reduce((total, item) => total + item.size, 0);
  const incomingBytes = files.reduce((total, file) => total + file.size, 0);
  if (currentBytes + incomingBytes > MAX_CHAT_IMAGE_TOTAL_BYTES) {
    throw new Error("图片总大小不能超过 20 MB");
  }

  for (const file of files) {
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
      throw new Error(`不支持图片格式：${file.name}，仅支持 JPG、PNG、WebP`);
    }
    if (file.size > MAX_CHAT_IMAGE_BYTES) {
      throw new Error(`图片 ${file.name} 超过 8 MB 限制`);
    }
  }

  const attachments = await Promise.all(
    files.map(async (file) => ({
      id: createAttachmentId(file),
      name: file.name,
      type: file.type,
      size: file.size,
      dataUrl: await readFileAsDataUrl(file),
    })),
  );
  return [...current, ...attachments];
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string" || !reader.result.startsWith("data:image/")) {
        reject(new Error(`无法读取图片：${file.name}`));
        return;
      }
      resolve(reader.result);
    };
    reader.onerror = () => reject(new Error(`无法读取图片：${file.name}`));
    reader.readAsDataURL(file);
  });
}

function createAttachmentId(file: File): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  return uuid || `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(16).slice(2)}`;
}
