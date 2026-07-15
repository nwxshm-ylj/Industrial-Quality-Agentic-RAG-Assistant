"""Validate release configuration without printing secret values."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


INSECURE_JWT_VALUES = {
    "",
    "change_me",
    "dev_secret_key_change_me",
}
PLACEHOLDER_MARKERS = (
    "change_me",
    "your_api_key",
    "replace_me",
    "example_secret",
)


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"环境文件不存在: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(values: dict[str, str], production: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def value(name: str, default: str = "") -> str:
        return values.get(name, os.getenv(name, default)).strip()

    required = ["DATABASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"]
    if value("EMBEDDING_PROVIDER", "qwen").lower() == "qwen":
        required.extend([
            "QWEN_EMBEDDING_API_KEY",
            "QWEN_EMBEDDING_MODEL",
            "QWEN_EMBEDDING_DIMENSION",
        ])
    for name in required:
        current = value(name)
        if is_placeholder(current):
            errors.append(f"{name} 未配置有效值")

    dimension = value("QWEN_EMBEDDING_DIMENSION", "1024")
    if not dimension.isdigit() or int(dimension) <= 0:
        errors.append("QWEN_EMBEDDING_DIMENSION 必须为正整数")

    alias = value("QDRANT_COLLECTION_ALIAS")
    collection = value("QDRANT_COLLECTION")
    if not alias:
        errors.append("QDRANT_COLLECTION_ALIAS 不能为空")
    if alias and alias == collection:
        errors.append("Qdrant Alias 与物理 Collection 名称不能相同")

    prompt_release = Path(value("PROMPT_RELEASE_PATH", "prompts/releases/stable.yaml"))
    if not prompt_release.exists():
        errors.append(f"Prompt Release 不存在: {prompt_release}")

    jwt_secret = value("JWT_SECRET_KEY")
    if jwt_secret in INSECURE_JWT_VALUES:
        (errors if production else warnings).append("JWT_SECRET_KEY 仍为开发默认值")
    elif production and len(jwt_secret) < 32:
        errors.append("生产 JWT_SECRET_KEY 长度至少应为 32 个字符")

    if production:
        postgres_values = {
            name: value(name)
            for name in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
        }
        for name, current in postgres_values.items():
            if is_placeholder(current):
                errors.append(f"{name} 未配置有效值")
        postgres_password = postgres_values["POSTGRES_PASSWORD"]
        if postgres_password and not re.fullmatch(r"[A-Za-z0-9._~-]+", postgres_password):
            errors.append(
                "POSTGRES_PASSWORD 必须使用 URL-safe 字符；"
                "建议使用 secrets.token_urlsafe 生成"
            )
        if value("ENVIRONMENT", "development").lower() != "production":
            errors.append("生产校验要求 ENVIRONMENT=production")
        database_url = value("DATABASE_URL")
        if "rag_password" in database_url:
            errors.append("生产 DATABASE_URL 仍使用演示数据库密码")
        try:
            parsed_database_url = urlsplit(database_url)
            database_user = unquote(parsed_database_url.username or "")
            database_password = unquote(parsed_database_url.password or "")
            database_name = parsed_database_url.path.lstrip("/")
            if database_user != postgres_values["POSTGRES_USER"]:
                errors.append("DATABASE_URL 用户名与 POSTGRES_USER 不一致")
            if database_password != postgres_password:
                errors.append("DATABASE_URL 密码与 POSTGRES_PASSWORD 不一致")
            if database_name != postgres_values["POSTGRES_DB"]:
                errors.append("DATABASE_URL 数据库名与 POSTGRES_DB 不一致")
        except ValueError:
            errors.append("DATABASE_URL 格式无效")
        if value("TELEMETRY_CAPTURE_CONTENT", "false").lower() == "true":
            warnings.append("生产环境启用了 TELEMETRY_CAPTURE_CONTENT，请确认数据合规")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    try:
        values = load_env_file(args.env_file) if args.env_file else {}
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        if args.env_file and args.env_file.name == ".env.production":
            print(
                "HINT: 请先执行 Copy-Item .env.production.example "
                ".env.production，并填写真实生产配置。"
            )
        raise SystemExit(2) from None
    errors, warnings = validate(values, production=args.production)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print({
        "status": "success",
        "mode": "production" if args.production else "development",
        "warnings": len(warnings),
    })


if __name__ == "__main__":
    main()
