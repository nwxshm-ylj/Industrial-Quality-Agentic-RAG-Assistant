from __future__ import annotations

import argparse
import json

from app.core.config import settings
from app.services.usage_service import UsageService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete observability usage facts older than the retention window."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=settings.usage_retention_days,
        help="Retention window in days",
    )
    args = parser.parse_args()
    try:
        result = UsageService().cleanup_old_data(args.days)
    except Exception as exc:
        raise RuntimeError(
            "Observability cleanup requires initialized PostgreSQL. "
            f"Original error: {exc}"
        ) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

