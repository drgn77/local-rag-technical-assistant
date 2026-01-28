import hashlib
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


def ensure_collection(client: QdrantClient, collection: str, dim: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def recreate_collection(client: QdrantClient, collection: str, dim: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        client.delete_collection(collection_name=collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def stable_point_id(payload: Dict[str, Any]) -> int:
    key = f"{payload.get('file_path','')}|{payload.get('chunk_id','')}|{payload.get('text','')}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def upsert_points(
    client: QdrantClient,
    collection: str,
    vectors: List[List[float]],
    payloads: List[Dict[str, Any]],
) -> int:
    points: List[PointStruct] = []
    for vec, payload in zip(vectors, payloads):
        pid = stable_point_id(payload)
        points.append(PointStruct(id=pid, vector=vec, payload=payload))

    client.upsert(collection_name=collection, points=points)
    return len(points)
