import { Tag, Tooltip } from "antd";

import { getDocumentStatus } from "./presentation";

export function DocumentStatusTag({ status }: { status: string }) {
  const presentation = getDocumentStatus(status);
  return (
    <Tooltip title={presentation.description}>
      <Tag color={presentation.color} bordered={false} className={`document-status document-status--${status}`}>
        <i />{presentation.label}
      </Tag>
    </Tooltip>
  );
}
