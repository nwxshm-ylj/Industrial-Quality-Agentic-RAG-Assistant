FROM python:3.11.11-slim-bookworm

WORKDIR /runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY deepdoc_runtime/requirements.txt /runtime/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --retries 5 --timeout 300 -r /runtime/requirements.txt

COPY deepdoc_runtime /runtime/deepdoc_runtime

EXPOSE 8010

CMD ["uvicorn", "deepdoc_runtime.main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]
