# API 调用示例

## 1. 基础地址与鉴权

本地 Docker 默认 API 地址：

```powershell
$env:API_BASE = "http://localhost:18000"
```

除登录和健康检查外，企业接口均需要 Bearer Token。以下示例使用 PowerShell 的 `curl.exe`，避免与 `Invoke-WebRequest` 别名混淆。

## 2. 登录

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/auth/login" `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"<your-admin-password>"}'
```

典型响应：

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "username": "admin",
    "role": "admin",
    "is_active": true
  }
}
```

把返回的 Token 保存到环境变量：

```powershell
$env:TOKEN = "eyJ..."
```

## 3. Agentic graph-chat

第一轮：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/graph-chat" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"轮毂识别异常可能是什么原因？","top_k":5,"session_id":"demo-session-001"}'
```

使用相同 session_id 连续追问：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/graph-chat" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"那优先排查哪个？","top_k":5,"session_id":"demo-session-001"}'
```

带元数据过滤：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/graph-chat" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"视觉识别异常如何排查？","top_k":5,"session_id":"filter-demo","retrieval_filters":{"doc_types":["FMEA","SOP"],"versions":["v1"]}}'
```

响应兼容字段：

```json
{
  "question": "轮毂识别异常可能是什么原因？",
  "answer": "...",
  "citations": [],
  "request_id": "...",
  "session_id": "demo-session-001",
  "memory_messages": [],
  "metadata": {
    "intent": "fault_diagnosis",
    "evidence_score": 0.83,
    "evidence_enough": true,
    "retry_count": 0,
    "total_latency_ms": 1520.3,
    "retrieval_mode": "hybrid",
    "degraded": false
  },
  "intent": "fault_diagnosis",
  "rewritten_query": "...",
  "contexts": []
}
```

## 4. 流式问答与节点进度

```powershell
curl.exe -N -X POST "$env:API_BASE/api/v1/graph-chat/stream" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"扭矩报警如何排查？","top_k":5,"session_id":"stream-demo"}'
```

接口使用 Server-Sent Events，事件包括阶段开始、节点完成、答案 token、最终 result 和 error。前端应以最终 `result` 事件为完整响应来源。

## 5. 多模态查询

仅当服务端启用了多模态索引时使用：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/graph-chat" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"图片中设备部件可能存在什么异常？","session_id":"mm-demo","multimodal_query":{"images":["https://example.com/equipment.jpg"]}}'
```

图片支持 HTTP(S) URL 或 `data:image/...` URI。未开启多模态时，系统保留文本检索结果并在 metadata 标记降级。

## 6. 上传和管理文档

上传：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/documents/upload" `
  -H "Authorization: Bearer $env:TOKEN" `
  -F "file=@data/raw_docs/ai_vision_fmea.md" `
  -F "doc_type=FMEA" `
  -F "version=v1"
```

列表：

```powershell
curl.exe "$env:API_BASE/api/v1/documents" `
  -H "Authorization: Bearer $env:TOKEN"
```

详情：

```powershell
curl.exe "$env:API_BASE/api/v1/documents/<doc_id>" `
  -H "Authorization: Bearer $env:TOKEN"
```

重建索引，仅 admin：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/documents/<doc_id>/reindex" `
  -H "Authorization: Bearer $env:TOKEN"
```

删除，仅 admin：

```powershell
curl.exe -X DELETE "$env:API_BASE/api/v1/documents/<doc_id>" `
  -H "Authorization: Bearer $env:TOKEN"
```

## 7. 提交反馈

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/feedback" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"request_id":"<graph-chat request_id>","session_id":"demo-session-001","question":"轮毂识别异常可能是什么原因？","answer":"...","rating":"positive","comment":"引用和排查顺序准确","intent":"fault_diagnosis","citations":[],"metadata":{}}'
```

反馈统计，admin/engineer：

```powershell
curl.exe "$env:API_BASE/api/v1/feedback/stats" `
  -H "Authorization: Bearer $env:TOKEN"
```

## 8. 评估接口

运行端到端评估：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/evaluation/run" `
  -H "Authorization: Bearer $env:TOKEN"
```

运行独立检索评估，不调用答案生成 LLM：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/evaluation/retrieval/run" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"top_k":5,"k_values":[1,3,5],"max_questions":null}'
```

运行 RAGAS 评估：

```powershell
curl.exe -X POST "$env:API_BASE/api/v1/evaluation/ragas/run" `
  -H "Authorization: Bearer $env:TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"max_questions":5}'
```

## 9. 可观测性与审计

```powershell
curl.exe "$env:API_BASE/api/v1/observability/requests/<request_id>" `
  -H "Authorization: Bearer $env:TOKEN"

curl.exe "$env:API_BASE/api/v1/observability/analytics/overview" `
  -H "Authorization: Bearer $env:TOKEN"

curl.exe "$env:API_BASE/api/v1/audit-logs?limit=50" `
  -H "Authorization: Bearer $env:TOKEN"
```

## 10. 健康检查

```powershell
curl.exe "$env:API_BASE/health"
curl.exe "$env:API_BASE/health/ready"
```

readiness 不调用真实收费 Embedding API；本地 BGE-M3 模式只检查模型目录和关键依赖状态。
