from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import settings


class IndustrialReranker:
    def __init__(self, model: Any | None = None):
        self.model_name = settings.reranker_model
        self.model = model or CrossEncoder(self.model_name)

    @staticmethod
    def _format_document(document: dict[str, Any]) -> str:
        """Build a source-aware reranker input without changing API payloads."""
        lines: list[str] = []
        source = str(document.get("source") or "").strip()
        doc_type = str(document.get("doc_type") or "").strip()
        heading_path = document.get("heading_path")
        page_number = document.get("page_number")
        page_start = document.get("page_start")
        page_end = document.get("page_end")

        if source:
            lines.append(f"[文档] {source}")
        if doc_type:
            lines.append(f"[文档类型] {doc_type}")
        if isinstance(heading_path, (list, tuple)):
            heading_text = " > ".join(
                str(value).strip()
                for value in heading_path
                if str(value).strip()
            )
        else:
            heading_text = str(heading_path or "").strip()
        if heading_text:
            lines.append(f"[章节] {heading_text}")

        if page_number is not None:
            lines.append(f"[页码] {page_number}")
        elif page_start is not None or page_end is not None:
            start = page_start if page_start is not None else page_end
            end = page_end if page_end is not None else page_start
            page_text = str(start) if start == end else f"{start}-{end}"
            lines.append(f"[页码] {page_text}")

        text = str(document.get("text") or "").strip()
        if text:
            lines.append(f"[正文]\n{text}")
        return "\n".join(lines)

    def rerank(
        self,
        question: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not documents:
            return []

        pairs = [
            [question, self._format_document(doc)]
            for doc in documents
        ]

        scores = self.model.predict(pairs)

        reranked_docs = []

        for doc, score in zip(documents, scores):
            reranked_docs.append({
                **doc,
                "rerank_score": float(score),
            })

        reranked_docs.sort(
            key=lambda x: x.get("rerank_score", 0.0),
            reverse=True
        )

        return reranked_docs[:top_k]
