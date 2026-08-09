from __future__ import annotations

import logging
import tempfile
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from deepdoc_runtime.engine import DeepDocEngine, load_engine
from deepdoc_runtime.settings import RuntimeSettings


logger = logging.getLogger("deepdoc_runtime")
logging.basicConfig(
    level=logging.INFO,
    format=(
        '{"level":"%(levelname)s","logger":"%(name)s",'
        '"message":"%(message)s"}'
    ),
)

app = FastAPI(title="Industrial RAG DeepDOC Runtime", version="1.0.0")


@lru_cache(maxsize=1)
def get_engine() -> DeepDocEngine:
    settings = RuntimeSettings.from_environment()
    return load_engine(settings.engine_factory)


@app.get("/health/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def readiness() -> dict[str, Any]:
    started_at = perf_counter()
    try:
        get_engine()
    except Exception as exc:
        logger.error(
            "deepdoc_runtime_not_ready error_type=%s error=%s",
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ) from exc
    return {
        "status": "ready",
        "engine": "infiniflow-deepdoc",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


@app.post("/v1/parse")
def parse_pdf(
    file: UploadFile = File(...),
    zoomin: int = Form(3),
    max_pages: int = Form(2000),
) -> dict[str, Any]:
    settings = RuntimeSettings.from_environment()
    if zoomin <= 0:
        raise HTTPException(status_code=400, detail="zoomin must be positive")
    if max_pages <= 0 or max_pages > settings.max_pages:
        raise HTTPException(
            status_code=400,
            detail=f"max_pages must be between 1 and {settings.max_pages}",
        )
    filename = Path(file.filename or "document.pdf").name
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="only PDF is supported")

    started_at = perf_counter()
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as target:
            temporary_path = Path(target.name)
            total_bytes = 0
            while True:
                block = file.file.read(1024 * 1024)
                if not block:
                    break
                total_bytes += len(block)
                if total_bytes > settings.max_file_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="PDF exceeds DeepDOC runtime size limit",
                    )
                target.write(block)
        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="PDF is empty")

        result = get_engine().parse_pdf(
            temporary_path,
            zoomin=zoomin,
            max_pages=max_pages,
        )
        logger.info(
            "deepdoc_parse_completed filename=%s bytes=%s latency_ms=%.2f",
            filename,
            total_bytes,
            (perf_counter() - started_at) * 1000,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "deepdoc_parse_failed filename=%s latency_ms=%.2f error=%s",
            filename,
            (perf_counter() - started_at) * 1000,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ) from exc
    finally:
        file.file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
