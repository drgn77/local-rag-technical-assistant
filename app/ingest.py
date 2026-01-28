import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from markdown_it import MarkdownIt

from config import QDRANT_URL, QDRANT_COLLECTION
from qdrant_store import ensure_collection, recreate_collection, upsert_points


SUPPORTED_EXT = {".txt", ".md", ".json"}


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def md_to_sections(md_text: str) -> List[Dict[str, str]]:
    md = MarkdownIt()
    tokens = md.parse(md_text)

    sections: List[Dict[str, str]] = []
    current_header = "ROOT"
    current_lines: List[str] = []

    def flush():
        nonlocal current_lines, current_header
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"header": current_header, "content": content})
        current_lines = []

    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            flush()
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            header_text = inline.content.strip() if inline and inline.type == "inline" else "HEADER"
            current_header = header_text
            i += 3
            continue

        if t.type == "inline":
            current_lines.append(t.content)
        elif t.type == "paragraph_open" or t.type == "paragraph_close":
            pass
        elif t.type == "fence":
            current_lines.append(t.content)
        i += 1

    flush()
    return sections


def flatten_json(obj: Any, prefix: str = "") -> List[str]:
    lines: List[str] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            lines.extend(flatten_json(v, new_prefix))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            new_prefix = f"{prefix}[{idx}]"
            lines.extend(flatten_json(v, new_prefix))
    else:
        val = obj
        if isinstance(val, str):
            val = val.replace("\n", "\\n").strip()
        lines.append(f"{prefix}={val}")

    return lines


def read_text(fp: Path) -> str:
    return fp.read_text(encoding="utf-8", errors="ignore")


def collect_chunks(data_dir: Path, chunk_size=900, chunk_overlap=150) -> Tuple[List[str], List[Dict[str, Any]]]:
    all_chunks: List[str] = []
    all_payloads: List[Dict[str, Any]] = []

    for fp in data_dir.rglob("*"):
        ext = fp.suffix.lower()
        if ext not in SUPPORTED_EXT:
            continue

        if ext == ".txt":
            text = read_text(fp)
            chunks = chunk_text(text, chunk_size, chunk_overlap)
            for i, ch in enumerate(chunks):
                all_chunks.append(ch)
                all_payloads.append(
                    {
                        "file_path": str(fp.relative_to(data_dir)),
                        "file_type": "txt",
                        "chunk_id": i,
                        "text": ch,
                    }
                )

        elif ext == ".md":
            md_text = read_text(fp)
            sections = md_to_sections(md_text)

            chunk_id = 0
            for sec in sections:
                header = sec["header"]
                content = sec["content"]

                chunks = chunk_text(content, chunk_size, chunk_overlap)
                for ch in chunks:
                    all_chunks.append(f"{header}\n{ch}".strip())
                    all_payloads.append(
                        {
                            "file_path": str(fp.relative_to(data_dir)),
                            "file_type": "md",
                            "header": header,
                            "chunk_id": chunk_id,
                            "text": ch,
                        }
                    )
                    chunk_id += 1

        elif ext == ".json":
            raw = read_text(fp)
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                chunks = chunk_text(raw, chunk_size, chunk_overlap)
                for i, ch in enumerate(chunks):
                    all_chunks.append(ch)
                    all_payloads.append(
                        {
                            "file_path": str(fp.relative_to(data_dir)),
                            "file_type": "json",
                            "chunk_id": i,
                            "text": ch,
                            "json_path": "RAW",
                        }
                    )
                continue

            lines = flatten_json(obj)
            joined = "\n".join(lines)
            chunks = chunk_text(joined, chunk_size, chunk_overlap)

            for i, ch in enumerate(chunks):
                all_chunks.append(ch)
                all_payloads.append(
                    {
                        "file_path": str(fp.relative_to(data_dir)),
                        "file_type": "json",
                        "chunk_id": i,
                        "text": ch,
                        "json_path": "FLATTENED",
                    }
                )

    return all_chunks, all_payloads

def ingest_folder_to_qdrant(data_dir: Path, reindex: bool = False) -> dict:
    client = QdrantClient(url=QDRANT_URL)
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    chunks, payloads = collect_chunks(data_dir)
    if not chunks:
        return {"indexed_files": 0, "indexed_chunks": 0}

    test_vec = list(next(embedder.embed(["test"])))
    dim = len(test_vec)

    if reindex:
        recreate_collection(client, QDRANT_COLLECTION, dim)
    else:
        ensure_collection(client, QDRANT_COLLECTION, dim)

    vectors = [list(v) for v in embedder.embed(chunks)]
    inserted = upsert_points(client, QDRANT_COLLECTION, vectors, payloads)

    indexed_files = len({p["file_path"] for p in payloads})
    return {"indexed_files": indexed_files, "indexed_chunks": inserted}
