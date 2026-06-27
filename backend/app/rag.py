from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


POLICY_DIR = Path(__file__).resolve().parent / "policies"
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_']+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "when",
    "with",
}


@dataclass
class PolicyChunk:
    title: str
    source: str
    text: str
    vector: Counter[str]
    norm: float


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(text.lower())
        if token not in STOP_WORDS and len(token) > 2
    ]


def _vectorize(text: str) -> Counter[str]:
    return Counter(_tokenize(text))


def _norm(vector: Counter[str]) -> float:
    return math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0


def _cosine(left: Counter[str], left_norm: float, right: Counter[str], right_norm: float) -> float:
    shared = set(left).intersection(right)
    if not shared:
        return 0.0
    dot = sum(left[token] * right[token] for token in shared)
    return dot / (left_norm * right_norm)


class PolicyRetriever:
    def __init__(self) -> None:
        self.chunks = self._load_chunks()

    def _load_chunks(self) -> list[PolicyChunk]:
        chunks: list[PolicyChunk] = []
        for path in sorted(POLICY_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            title = text.splitlines()[0].replace("#", "").strip()
            paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
            for paragraph in paragraphs:
                if paragraph.startswith("#"):
                    continue
                vector = _vectorize(f"{title} {paragraph}")
                chunks.append(
                    PolicyChunk(
                        title=title,
                        source=path.name,
                        text=paragraph,
                        vector=vector,
                        norm=_norm(vector),
                    )
                )
        return chunks

    def search(self, query: str, k: int = 3) -> list[dict[str, str | float]]:
        query_vector = _vectorize(query)
        query_norm = _norm(query_vector)
        scored = [
            (
                _cosine(chunk.vector, chunk.norm, query_vector, query_norm),
                chunk,
            )
            for chunk in self.chunks
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        results: list[dict[str, str | float]] = []
        for score, chunk in scored[:k]:
            if score <= 0:
                continue
            results.append(
                {
                    "title": chunk.title,
                    "source": chunk.source,
                    "text": chunk.text,
                    "score": round(score, 3),
                }
            )
        return results

    def list_policies(self) -> list[dict[str, str]]:
        policies: list[dict[str, str]] = []
        for path in sorted(POLICY_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            title = text.splitlines()[0].replace("#", "").strip()
            policies.append({"title": title, "source": path.name, "text": text})
        return policies


retriever = PolicyRetriever()
