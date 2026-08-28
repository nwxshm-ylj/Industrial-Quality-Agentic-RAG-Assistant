import { useState } from "react";
import {
  Button,
  Input,
  Progress,
  Select,
  Typography,
  Upload,
  type UploadFile,
  type UploadProps,
} from "antd";

const { Dragger } = Upload;

export type UploadDocumentType =
  | "LESSON_LEARNED"
  | "STANDARD_WORK_DOCUMENT"
  | "PFMEA"
  | "AFTERSALES_DOCUMENT";

interface DocumentUploadPanelProps {
  loading: boolean;
  progress: number;
  onUpload: (
    file: File,
    docType: UploadDocumentType,
    version: string,
  ) => Promise<void>;
}

const docTypeOptions: Array<{
  label: string;
  value: UploadDocumentType;
}> = [
  { label: "LessonLearn", value: "LESSON_LEARNED" },
  { label: "标准作业文档", value: "STANDARD_WORK_DOCUMENT" },
  { label: "PFMEA", value: "PFMEA" },
  { label: "售后文档", value: "AFTERSALES_DOCUMENT" },
];

export function DocumentUploadPanel({
  loading,
  progress,
  onUpload,
}: DocumentUploadPanelProps) {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [docType, setDocType] = useState<UploadDocumentType>();
  const [version, setVersion] = useState("v1");

  const uploadProps: UploadProps = {
    accept: ".md,.txt,.pdf,.docx,.pptx",
    maxCount: 1,
    multiple: false,
    fileList,
    disabled: loading,
    beforeUpload: (file) => {
      setFileList([file]);
      return false;
    },
    onRemove: () => {
      setFileList([]);
    },
  };

  const submit = async () => {
    const selected = fileList[0];
    const file = selected?.originFileObj
      || (selected as unknown as File | undefined);
    if (!file || !docType) {
      return;
    }
    try {
      await onUpload(file, docType, version);
      setFileList([]);
    } catch {
      // 上层统一展示 API 错误，并保留所选文件以便重试。
    }
  };

  return (
    <section className="kb-upload-panel">
      <div className="kb-section-heading">
        <div>
          <Typography.Text className="panel-kicker">
            INGEST DOCUMENT
          </Typography.Text>
          <Typography.Title level={4}>上传并建立知识索引</Typography.Title>
        </div>
        <span className="kb-sequence">01</span>
      </div>

      <Dragger {...uploadProps}>
        <div className="upload-symbol"><span>↑</span></div>
        <p className="ant-upload-text">拖拽文档到这里，或点击选择</p>
        <p className="ant-upload-hint">
          支持 MD / TXT / PDF / DOCX / PPTX，单次上传一个文件
        </p>
      </Dragger>

      <div className="upload-metadata-grid">
        <label>
          <span>文档标签（必选）</span>
          <Select<UploadDocumentType>
            value={docType}
            options={docTypeOptions}
            onChange={setDocType}
            disabled={loading}
            placeholder="请选择文档标签"
          />
        </label>
        <label>
          <span>版本</span>
          <Input
            value={version}
            maxLength={50}
            disabled={loading}
            onChange={(event) => setVersion(event.target.value)}
          />
        </label>
      </div>

      {loading && (
        <div className="upload-progress">
          <span>
            <b>上传与索引处理中</b>
            <small>
              {progress < 100 ? "正在传输文件" : "正在解析并写入知识索引"}
            </small>
          </span>
          <Progress
            percent={progress}
            showInfo={false}
            strokeColor="#0f766e"
          />
        </div>
      )}

      <Button
        block
        type="primary"
        loading={loading}
        disabled={fileList.length === 0 || !docType || !version.trim()}
        onClick={submit}
      >
        上传并入库
      </Button>

      <div className="upload-lifecycle-note">
        <b>INDEX CONTRACT</b>
        <p>
          文档标签将写入 PostgreSQL、Qdrant、OpenSearch，并参与后续追溯检索。
          只有索引链路全部成功后，文档状态才会标记为 indexed。
        </p>
      </div>
    </section>
  );
}
