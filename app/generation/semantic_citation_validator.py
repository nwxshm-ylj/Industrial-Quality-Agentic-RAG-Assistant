from __future__ import annotations

import json
import re
from typing import Any, Protocol

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.observability.model_usage import invoke_observed_chat_model
from app.prompting import get_prompt_registry


_JSON_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_VERDICTS = {"supported", "partial", "unsupported"}


class SemanticCitationVerifier(Protocol):
    def verify(
        self,
        *,
        question: str,
        claims: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


class LLMSemanticCitationVerifier:
    """Batch-verify all claim/citation pairs with one observed LLM call."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
            max_tokens=2048,
        )

    def verify(
        self,
        *,
        question: str,
        claims: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = self._build_payload(claims, contexts)
        if not payload:
            return {"claims": []}

        rendered_prompt = get_prompt_registry().render(
            "semantic_citation_verifier",
            {
                "question": question,
                "claim_evidence_json": json.dumps(
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
            },
        )
        response = invoke_observed_chat_model(
            self.llm,
            list(rendered_prompt.messages),
            component="semantic_citation_verifier",
            provider=settings.llm_provider,
            model_name=settings.llm_model,
            prompt_reference=rendered_prompt.reference,
        )
        content = self._content_to_text(response.content)
        return self._parse_response(content, expected_claims=payload)

    @staticmethod
    def _build_payload(
        claims: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        context_by_label = {
            str(context.get("citation_label") or f"资料{index}"): context
            for index, context in enumerate(contexts, start=1)
        }
        payload: list[dict[str, Any]] = []
        for index, claim in enumerate(claims):
            citation_ids = [
                str(value)
                for value in claim.get("citation_ids", [])
                if value
            ]
            evidence = []
            for citation_id in citation_ids:
                context = context_by_label.get(citation_id)
                if context is None:
                    continue
                evidence.append(
                    {
                        "citation_id": citation_id,
                        "source": context.get("source"),
                        "text": str(context.get("text") or "")[:12000],
                    }
                )
            if evidence:
                payload.append(
                    {
                        "claim_index": index,
                        "claim": str(claim.get("text") or ""),
                        "evidence_policy": str(
                            claim.get("evidence_policy") or "standard"
                        ),
                        "claim_category": str(
                            claim.get("claim_category") or "fact"
                        ),
                        "citation_required": bool(
                            claim.get("citation_required", True)
                        ),
                        "evidence": evidence,
                    }
                )
        return payload

    @staticmethod
    def _content_to_text(content: object) -> str:
        if isinstance(content, list):
            return "\n".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content or "")

    @classmethod
    def _parse_response(
        cls,
        content: str,
        *,
        expected_claims: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stripped = content.strip()
        fence_match = _JSON_FENCE_PATTERN.match(stripped)
        if fence_match:
            stripped = fence_match.group(1).strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("semantic verifier did not return a JSON object")
            parsed = json.loads(stripped[start : end + 1])

        raw_results = parsed.get("claims") if isinstance(parsed, dict) else None
        if not isinstance(raw_results, list):
            raise ValueError("semantic verifier response is missing claims")

        expected_indexes = {
            int(item["claim_index"]) for item in expected_claims
        }
        normalized: dict[int, dict[str, Any]] = {}
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            try:
                claim_index = int(item.get("claim_index"))
            except (TypeError, ValueError):
                continue
            if claim_index not in expected_indexes:
                continue
            verdict = str(item.get("verdict") or "").strip().lower()
            if verdict not in _ALLOWED_VERDICTS:
                continue
            normalized[claim_index] = {
                "claim_index": claim_index,
                "verdict": verdict,
                "reason": str(item.get("reason") or "").strip()[:1000],
            }

        missing = sorted(expected_indexes - set(normalized))
        if missing:
            raise ValueError(
                "semantic verifier omitted claim indexes: "
                + ", ".join(str(value) for value in missing)
            )
        return {
            "claims": [normalized[index] for index in sorted(normalized)]
        }
