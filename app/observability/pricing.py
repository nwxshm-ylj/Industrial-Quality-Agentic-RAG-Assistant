from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import yaml

@dataclass(frozen=True)
class CalculatedCost:
    amount: float
    currency: str
    pricing_version: str


class ModelPriceCatalog:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        data = payload or {}
        self.version = str(data.get("version", "unpriced"))
        self.currency = str(data.get("currency", "CNY"))
        self.models = data.get("models", {}) or {}

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelPriceCatalog":
        price_path = Path(path)
        if not price_path.exists():
            return cls()
        with price_path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file) or {}
        if not isinstance(payload, dict):
            raise ValueError("model pricing file must contain a YAML mapping")
        return cls(payload)

    def calculate(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> CalculatedCost | None:
        model_key = f"{provider}:{model}"
        price = self.models.get(model_key)
        if not isinstance(price, dict):
            return None

        input_rate = price.get(
            "embedding_price_per_1k_tokens"
            if operation.startswith("embedding_")
            else "input_price_per_1k_tokens"
        )
        output_rate = price.get("output_price_per_1k_tokens", 0)
        if input_rate is None:
            return None

        amount = (
            max(input_tokens or 0, 0) * float(input_rate)
            + max(output_tokens or 0, 0) * float(output_rate)
        ) / 1000
        return CalculatedCost(
            amount=round(amount, 8),
            currency=str(price.get("currency", self.currency)),
            pricing_version=str(price.get("version", self.version)),
        )


@lru_cache(maxsize=1)
def get_model_price_catalog() -> ModelPriceCatalog:
    return ModelPriceCatalog.from_file(
        os.getenv("MODEL_PRICING_PATH", "data/config/model_pricing.yaml")
    )


def clear_model_price_catalog_cache() -> None:
    get_model_price_catalog.cache_clear()
