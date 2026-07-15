import { useState } from "react";
import {
  AutoComplete,
  Button,
  Input,
  Progress,
  Typography,
  Upload,
  type UploadFile,
  type UploadProps,
} from "antd";

const { Dragger } = Upload;

interface DocumentUploadPanelProps {
  loading: boolean;
  progress: number;
  onUpload: (file: File, docType: string, version: string) => Promise<void>;
}

const docTypeOptions = ["SOP", "FMEA", "RULE", "CASE", "QUALITY_STANDARD"].map((value) => ({
  label: value,
  value,
}));

export function DocumentUploadPanel({
  loading,
  progress,
  onUpload,
}: DocumentUploadPanelProps) {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [docType, setDocType] = useState<string>("SOP");
  const [version, setVersion] = useState("v1");

  const uploadProps: UploadProps = {
    accept: ".md,.txt,.pdf,.docx",
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
    const file = selected?.originFileObj || (selected as unknown as File | undefined);
    if (!file) {
      return;
    }
    try {
      await onUpload(file, docType, version);
      setFileList([]);
    } catch {
      // Parent mutation renders the normalized API error and keeps the file selected for retry.
    }
  };

  return (
    <section className="kb-upload-panel">
      <div className="kb-section-heading">
        <div>
          <Typography.Text className="panel-kicker">INGEST DOCUMENT</Typography.Text>
          <Typography.Title level={4}>上传并建立双索引</Typography.Title>
        </div>
        <span className="kb-sequence">01</span>
      </div>

      <Dragger {...uploadProps}>
        <div className="upload-symbol"><span>↑</span></div>
        <p className="ant-upload-text">拖拽文档到这里，或点击选择</p>
        <p className="ant-upload-hint">MD / TXT / PDF / DOCX · 单文件上传</p>
      </Dragger>

      <div className="upload-metadata-grid">
        <label>
          <span>文档类型</span>
          <AutoComplete
            value={docType}
            options={docTypeOptions}
            onChange={setDocType}
            disabled={loading}
            placeholder="SOP / FMEA / 自定义类型"
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
          <span><b>上传与索引处理中</b><small>{progress < 100 ? "正在传输文件" : "正在解析并写入双索引"}</small></span>
          <Progress percent={progress} showInfo={false} strokeColor="#0a8f86" />
        </div>
      )}

      <Button
        block
        type="primary"
        loading={loading}
        disabled={fileList.length === 0 || !version.trim()}
        onClick={submit}
      >
        上传并入库
      </Button>

      <div className="upload-lifecycle-note">
        <b>INDEX CONTRACT</b>
        <p>只有 PostgreSQL、Qdrant 与 OpenSearch 全部成功后，状态才会显示为 indexed。</p>
      </div>
    </section>
  );
}
