from typing import List, Dict, Any, Tuple

from qdrant_client import QdrantClient
from fastembed import TextEmbedding

from config import QDRANT_URL, QDRANT_COLLECTION


_EMBEDDER = TextEmbedding("BAAI/bge-small-en-v1.5")


def _embed_query(text: str) -> List[float]:
    vec = next(_EMBEDDER.embed([text]))
    return vec.tolist() if hasattr(vec, "tolist") else list(vec)


def search_qdrant(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    client = QdrantClient(url=QDRANT_URL)
    query_vec = _embed_query(question)

    res = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vec,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    hits: List[Dict[str, Any]] = []
    for p in res.points:
        payload = p.payload or {}
        hits.append(
            {
                "file_path": payload.get("file_path", "unknown"),
                "chunk_id": payload.get("chunk_id", -1),
                "score": float(p.score or 0.0),
                "excerpt": payload.get("text", "") or payload.get("excerpt", ""),
            }
        )
    return hits


def _clean_excerpt(text: str, max_len: int = 240) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def _dedupe_and_sort_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[Tuple[str, int], Dict[str, Any]] = {}

    for h in hits:
        key = (str(h.get("file_path", "")), int(h.get("chunk_id", -1)))
        if key not in best or float(h.get("score", 0)) > float(best[key].get("score", 0)):
            best[key] = h

    out = list(best.values())
    out.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return out


def build_context(hits: List[Dict[str, Any]], max_chars: int = 1800) -> str:
    hits = _dedupe_and_sort_hits(hits)

    blocks: List[str] = []
    total = 0

    for h in hits:
        file_path = h.get("file_path", "?")
        chunk_id = h.get("chunk_id", "?")
        score = float(h.get("score", 0))
        excerpt = _clean_excerpt(str(h.get("excerpt", "")))

        block = f"[{file_path} | chunk={chunk_id} | score={score:.3f}] {excerpt}"
        if total + len(block) + 1 > max_chars:
            break

        blocks.append(block)
        total += len(block) + 1

    return "\n".join(blocks)
