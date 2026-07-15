# Enterprise Release Guide

## Release Scope

The release gate validates source integrity, frontend behavior, container
configuration, environment safety, and rollback readiness. It does not invoke
real LLM or paid embedding APIs by default.

## Validation Tiers

### Fast quality gate

```bash
python -m scripts.release_check
```

This runs Python compilation, Compose validation, whitespace checks, React
typechecking, unit tests, and the production frontend build.

### Mocked browser E2E

Install Chromium once:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

On a Windows workstation with Chrome already installed, the bundled browser
download can be skipped:

```powershell
$env:PLAYWRIGHT_CHANNEL = "chrome"
npm run test:e2e
Remove-Item Env:\PLAYWRIGHT_CHANNEL
```

The browser tests mock FastAPI responses and cover login, RBAC navigation,
chat, feedback, user management, audit logs, and readiness. They do not need
PostgreSQL, Qdrant, OpenSearch, an LLM, or an embedding API.

### Docker integration

```bash
docker compose up -d --build
docker compose exec api python -m scripts.test_admin_console
docker compose exec api python -m scripts.test_auth_rbac
docker compose exec api python -m scripts.test_document_management
docker compose exec api python -m scripts.test_feedback_evaluation
```

Model-dependent tests remain manual and must not run in the default CI gate.

## Production Configuration Check

Validate a candidate environment without printing secret values:

```powershell
Copy-Item .env.production.example .env.production
# Edit .env.production and replace every CHANGE_ME value.
python -m scripts.validate_release_env --env-file .env.production --production
```

The real `.env.production` file is intentionally ignored by Git and is not
created automatically because it must contain deployment-specific secrets.
For the bundled PostgreSQL container, `POSTGRES_PASSWORD` must match the
password in `DATABASE_URL`. Use a URL-safe password because Compose builds the
container connection string from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and
`POSTGRES_DB`.

The command rejects missing model credentials, insecure JWT defaults, demo
database passwords, missing Qdrant aliases, invalid embedding dimensions, and
missing Prompt Release manifests.

## Versioning

Before creating a tag:

1. Update the React package version and immutable Docker image tag.
2. Record the API image digest and React image digest.
3. Record the Prompt Release ID and Qdrant Alias target.
4. Export the environment-variable names in use without secret values.
5. Back up PostgreSQL and verify the restore procedure in a non-production environment.

Recommended tag format:

```text
v1.0.0
```

## Deployment

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health/ready
curl http://localhost:30080/healthz
```

Do not switch a Qdrant Alias or mark documents indexed until both vector and
keyword indexes have passed their own validation.

## Rollback

Rollback is an image and configuration operation, not a destructive data reset:

1. Stop new document uploads and evaluation runs.
2. Restore the previously recorded API and React image tags.
3. Restore the previous Prompt Release manifest.
4. Point `industrial_docs_active` only to the last validated Qdrant collection.
5. Run `/health/ready` and the admin console smoke test.
6. Resume traffic after PostgreSQL, Qdrant, OpenSearch, auth, and graph-chat checks pass.

Never delete the new Qdrant collection during rollback. Retain it for diagnosis
until the incident review is complete.
