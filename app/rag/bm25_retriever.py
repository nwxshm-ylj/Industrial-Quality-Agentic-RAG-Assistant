import re
from rank_bm25 import BM25Okapi

from app.rag.chunk_store import load_chunks


class BM25Retriever:
    def __init__(self):
        self.chunks = load_chunks()
        self.tokenized_corpus = [
            self._tokenize(chunk["text"])
            for chunk in self.chunks
        ]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        query_tokens = self._tokenize(query)

        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda idx: scores[idx],
            reverse=True
        )[:top_k]

        results = []

        for idx in ranked_indices:
            score = float(scores[idx])
            chunk = self.chunks[idx]

            if score <= 0:
                continue

            metadata = chunk.get("metadata", {})

            results.append({
                "text": chunk.get("text", ""),
                "source": metadata.get("source", ""),
                "doc_type": metadata.get("doc_type", ""),
                "chunk_id": metadata.get("chunk_id", ""),
                "score": score,
                "retrieval_source": "bm25"
            })

        return results

    def _tokenize(self, text: str) -> list[str]:
        """
        面向工业文本的简单 tokenizer：
        1. 保留英文、数字、工位号、PR号等连续 token；
        2. 中文使用单字 + bigram，避免不安装 jieba；
        3. 统一小写。
        """
        text = text.lower()

        # 提取英文、数字、编号类 token，例如 zp8, pr001, tq001, cam001
        ascii_tokens = re.findall(r"[a-zA-Z]+[a-zA-Z0-9_]*|\d+(?:\.\d+)?", text)

        # 提取中文字符
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)

        # 中文 bigram
        chinese_bigrams = [
            chinese_chars[i] + chinese_chars[i + 1]
            for i in range(len(chinese_chars) - 1)
        ]

        return ascii_tokens + chinese_chars + chinese_bigrams