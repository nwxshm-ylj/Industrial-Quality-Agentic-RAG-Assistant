# 企业版发布与回滚指南

## 1. 发布目标

发布门禁检查源代码、前端构建、容器配置、环境安全、索引兼容和回滚准备。默认门禁不调用真实 LLM、在线 Embedding 或其他收费 API。

## 2. 快速质量门禁

```powershell
python -m scripts.release_check
```

该脚本组合执行 Python 编译、Compose 校验、空白检查、React 类型检查、单元测试和前端生产构建。

单独检查：

```powershell
python -m compileall app scripts
docker compose config --quiet
git diff --check
```

## 3. 前端 E2E

```powershell
Set-Location frontend
npm.cmd ci
npx playwright install chromium
npm.cmd run test:e2e
```

已有本地 Chrome 时：

```powershell
$env:PLAYWRIGHT_CHANNEL = "chrome"
npm.cmd run test:e2e
Remove-Item Env:\PLAYWRIGHT_CHANNEL
```

Mock E2E 覆盖登录、RBAC、聊天、反馈、用户管理、审计和 readiness，不依赖 PostgreSQL、Qdrant、OpenSearch 或 LLM。

## 4. Docker 集成门禁

```powershell
docker compose --profile deepdoc up -d --build
docker compose exec api python -m scripts.test_admin_console
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_memory
docker compose exec api python -m scripts.test_observability
docker compose exec api python -m scripts.test_feedback_evaluation
```

检索集成：

```powershell
docker compose exec api python -m scripts.evaluate_retrieval
```

RAGAS、DeepDOC Live、多模态真实模型和端到端 LLM 评估属于人工验收，不进入默认 CI。

## 5. 生产环境检查

```powershell
Copy-Item .env.production.example .env.production
# 替换全部 CHANGE_ME
python -m scripts.validate_release_env --env-file .env.production --production
```

检查项包括：

- JWT Secret 和默认密码；
- PostgreSQL 密码与 DATABASE_URL；
- Qdrant Collection/Alias；
- Embedding 模型、维度和本地路径；
- Prompt Release；
- 必要外部服务地址；
- 生产模式下的不安全默认值。

## 6. 索引发布

Embedding、Chunk、Parser 或 Payload 结构变化时，不允许直接覆盖活动 Collection：

1. 创建新的版本化 Qdrant Collection；
2. 构建对应 OpenSearch 索引；
3. 验证双路数量；
4. 运行独立检索评估；
5. 记录旧 Alias 目标；
6. 切换稳定 Alias；
7. 启动 API 并执行 smoke test；
8. 观察错误率、降级率和延迟。

旧 Collection 保留到观察期结束，不在发布脚本中删除。

## 7. 版本标识

发布前检查：

- React package version；
- Docker Image Tag，不使用 latest 作为正式发布标识；
- `OTEL_SERVICE_VERSION`；
- Prompt Release；
- Embedding index version；
- Keyword index version；
- parser_version 和 chunk_strategy；
- 数据库迁移版本。

## 8. 回滚

### 应用回滚

使用上一个不可变镜像 Tag 重新部署，不在运行容器内修改源码。

### 向量索引回滚

把 `industrial_docs_active` Alias 指回发布前记录的旧 Collection。不要删除失败的新 Collection，先保留用于排查。

### OpenSearch 回滚

当前关键词索引由版本配置选择。回滚应用时同步恢复对应 keyword index version，避免应用与索引 schema 不一致。

### 数据库回滚

数据库结构变更必须有独立 migration 和 downgrade 方案。`scripts/init_sql_data.py` 是样例初始化脚本，不承担正式生产回滚。

## 9. 发布记录

每次发布至少保存：

- Git Commit/Tag；
- Docker Image Digest；
- 环境配置版本，不含密钥；
- Prompt Release；
- Qdrant Alias 新旧目标；
- OpenSearch 索引版本；
- 回归报告和检索评估 run_id；
- 发布时间、负责人和回滚决策。
