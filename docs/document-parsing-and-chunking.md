# 文档解析与 Chunk 切分策略

## 1. 设计目标

知识库入库不再把所有格式简单压平成一段文本，而是在不改变现有 API、数据库表和索引生命周期的前提下，保留以下信息：

- Markdown、DOCX 的标题层级；
- PDF 的页码和阅读顺序；
- PPTX 的页码、标题、文本框和表格；
- Markdown、DOCX、PDF、PPTX 中可提取的表格结构；
- 章节和页码上下文，便于检索结果独立理解和引用。

## 2. 参考实现分析

本实现参考了 `FinInsRAG-V3` 中 DeepDOC/RAGFlow 风格解析链路的设计思想：

1. 按文件格式选择解析器，而不是使用一个通用文本读取器；
2. 将连续正文与表格分开处理；
3. 表格保留表头，并按数据行组成可检索文本；
4. 使用标题、页码和版面顺序作为 Chunk 边界；
5. 解析结果先形成统一结构，再交给切分和索引层。

项目没有把参考仓库的 DeepDOC 源码、模型文件和自动下载逻辑直接打进 API 镜像，而是增加了可选的 `DeepDocParserAdapter` 和独立 `deepdoc-runtime` 服务：

- API 通过 `DEEPDOC_RUNTIME_URL` 调用版本化 HTTP 协议，不暴露 DeepDOC SDK 类型；
- DeepDOC 模型只在 sidecar 进程内初始化一次，并在请求之间复用；参考解析器具有可变状态，因此解析调用使用进程内锁保护；
- 源码和模型以只读卷挂载，运行时强制 Hugging Face 离线模式，不在请求期间下载模型；
- 启动解析前校验本地模型目录与必需模型文件，缺失时快速失败；
- DeepDOC 输出统一转换为 `ParsedDocument/DocumentElement`，再进入现有切分与双索引链路；
- `auto` 模式下仅 PDF 优先使用 DeepDOC，失败时可回退 `structured-v1`；
- 不在默认测试中加载 DeepDOC 模型或访问 Hugging Face。

原有 `DEEPDOC_RUNTIME_FACTORY=module:attribute` 本地工厂方式仍作为兼容入口保留，但 Docker 部署优先使用隔离的 HTTP sidecar。原有 PyMuPDF、python-docx、python-pptx、Dots.OCR 和多模态资产链路继续保留。

启用时的配置入口如下：

```text
DOCUMENT_PARSER_BACKEND=auto
DOCUMENT_PARSER_FALLBACK=native
DEEPDOC_ENABLED=true
DEEPDOC_RUNTIME_URL=http://deepdoc-runtime:8010
DEEPDOC_CONNECT_TIMEOUT_SECONDS=5
DEEPDOC_READ_TIMEOUT_SECONDS=300
DEEPDOC_HEALTH_TIMEOUT_SECONDS=2
DEEPDOC_ZOOMIN=3
DEEPDOC_MAX_PAGES=2000
```

sidecar 模型目录至少需要 `det.onnx`、`rec.onnx`、`ocr.res`、`layout.onnx`、`tsr.onnx` 和 `updown_concat_xgb.model`。仓库不会提交这些大文件，也不会在 API 请求期间自动下载资源。

### 结构化解析与多模态合并

当 `MULTIMODAL_ENABLED=true` 时，系统不会在结构化结果和多模态结果之间二选一：

1. DeepDOC/原生解析结果负责标题层级、正文顺序、表格、页码和 bbox；
2. 多模态解析结果负责页面/幻灯片资产、OCR 补充文本和 `asset_id`；
3. 相同页面的结构化元素关联该页全部 `asset_ids`；
4. 已存在于结构化正文的原生文本不会重复添加；
5. 仅 OCR 新增的内容形成 `ocr_text` 元素；
6. Chunk 汇总关联的 `asset_ids`，供多模态引用与后续图文检索使用。

合并后的 parser 版本采用组合标识，例如 `deepdoc-layout-v1+multimodal-v1`，便于索引溯源和重建判断。

## 3. 解析结果协议

`load_single_document()` 保持原有 `source/content/file_ext` 字段，并增加：

```python
{
    "source": "wheel_sop.docx",
    "content": "完整可检索文本",
    "file_ext": ".docx",
    "parser": "structured-v1",
    "sections": [
        {
            "text": "轮毂识别异常",
            "section_type": "heading",
            "heading_path": ["轮毂识别异常"],
            "heading_level": 1,
            "page_number": None,
            "table_index": None,
        }
    ],
}
```

新增字段是向后兼容的；只读取原三个字段的调用方不受影响。

## 4. 各格式解析策略

### Markdown

- 识别 `#` 到 `######` 标题；
- 维护章节路径；
- Markdown 表格作为独立 section；
- 普通段落按照空行形成 section。

### TXT

- 支持 UTF-8、UTF-8 BOM 和 GB18030；
- 识别“第一章”“第 2 节”“1.2”等编号标题；
- 其余内容按段落保留。

### DOCX

- 按 XML 正文顺序遍历段落和表格，避免先读取全部段落、再读取全部表格导致顺序丢失；
- 根据 Heading/标题样式和编号标题识别层级；
- 表格转换为 Markdown 表格，保留表头和行列关系。

### PDF

- 使用 PyMuPDF 按页面、从上到下提取文本块；
- 每个 section 保存页码；
- 运行时支持 `Page.find_tables()` 时，表格独立转换为 Markdown，并避免重复保留表格区域文本；
- 扫描版 PDF 仍由现有 Dots.OCR/多模态链路处理。

### PPTX

- 按幻灯片和形状坐标恢复阅读顺序；
- 幻灯片标题作为章节上下文；
- 文本框和组合形状递归提取；
- 表格独立转换为 Markdown。

## 5. Chunk 策略

知识库上传默认使用布局感知的 Token 预算：

```text
DOCUMENT_CHUNK_STRATEGY=layout_token_v2
DOCUMENT_CHUNK_TARGET_TOKENS=384
DOCUMENT_CHUNK_MAX_TOKENS=512
DOCUMENT_CHUNK_OVERLAP_TOKENS=48
```

第一版使用可替换的离线 `UnicodeTokenCounter` 做确定性 Token 预算估算，不下载 tokenizer 模型，也不调用在线 API。`TokenCounter` 是独立接口，后续可以接入与实际 Embedding/LLM 一致的 tokenizer。显式选择 `structured_char_v1` 或传入旧的字符切分参数时，仍保留原字符切分兼容路径。

切分规则：

1. 标题不单独形成低信息量 Chunk，而是作为后续正文的章节前缀；
2. PDF/PPTX 默认不跨页合并正文，DeepDOC 给出跨页位置时保留页码范围；
3. 同一章节、同一页内的短段落先合并，再递归切分；
4. 表格与正文分开；
5. 小表格保持完整；
6. 大表格按数据行拆分，每个子 Chunk 重复表头；
7. Chunk 文本显式加入章节与页码上下文，使 Qdrant 和 OpenSearch 两路索引都能检索这些信息；
8. Chunk 保存稳定 `chunk_id`、`content_hash`、parser/chunker 版本、element IDs、页码范围、bbox、表格标识和多模态 asset IDs。

## 6. 兼容边界

- `scripts/ingest_docs.py` 使用的 `load_markdown_docs()` 不变；
- 没有 `sections` 的旧文档继续使用原有 500/80 RecursiveCharacterTextSplitter；
- DocumentService 上传、删除、重建、PostgreSQL、Qdrant、OpenSearch 和多模态资产生命周期不变；
- 未新增数据库字段；
- 未修改 `/api/v1/graph-chat` 响应；
- 未调用真实 Embedding/OCR API 进行默认单元测试。

## 7. 验证

快速验证：

```bash
python -m scripts.test_document_parsing
python -m scripts.test_document_parser_contract
python -m scripts.test_deepdoc_parser_adapter
python -m scripts.test_parser_multimodal_merge
python -m scripts.test_layout_chunker
python -m scripts.test_deepdoc_http_runtime
python -m scripts.test_deepdoc_runtime_api
python -m compileall app scripts deepdoc_runtime
```

依赖 PostgreSQL、Qdrant、OpenSearch 的生命周期验证：

```bash
python -m scripts.test_document_management
```

修改 Chunk 策略后，历史已入库文档不会自动变化，需要对指定文档执行 reindex，或在测试环境执行批量重建后再比较 Recall@K、MRR 和 nDCG。

## 8. DeepDOC Sidecar 部署

首次部署前，从已获得合法授权的 DeepDOC/FinInsRAG 源码目录准备运行资源。该命令只复制最小源码集合及本地模型，不下载网络资源；生成目录已被 Git 和 Docker 构建上下文忽略：

```bash
python -m scripts.prepare_deepdoc_runtime --source-root /path/to/service/core
```

构建并启动可选 profile：

```bash
docker compose --profile deepdoc build deepdoc-runtime
docker compose --profile deepdoc up -d deepdoc-runtime
curl http://localhost:18010/health/ready
python -m scripts.test_deepdoc_runtime_live --base-url http://localhost:18010
```

Docker 网络内 API 使用 `http://deepdoc-runtime:8010`，宿主机验收端口默认为 `18010`，可通过 `DEEPDOC_RUNTIME_PORT` 调整。若希望知识库上传优先走 DeepDOC，需要同时配置：

```text
DEEPDOC_ENABLED=true
DOCUMENT_PARSER_BACKEND=auto
DOCUMENT_PARSER_FALLBACK=native
DEEPDOC_RUNTIME_URL=http://deepdoc-runtime:8010
```

`/health/ready` 仅检查 sidecar 引擎就绪状态，不执行文档推理。DeepDOC 不可用且 `DOCUMENT_PARSER_FALLBACK=native` 时，API readiness 标记为 degraded 并允许 PDF 回退到原生解析；若禁用回退，则解析失败会直接暴露为明确错误。
