import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI

from schemas import IngestRequest, IngestResponse, AskRequest, AskResponse, Source, LLMJson
from ingest import ingest_folder_to_qdrant
from retrieval import search_qdrant, build_context
from ollama_client import generate

app = FastAPI()


def _clean_excerpt(text: str, max_len: int = 240) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def parse_llm_json(s: str) -> Dict[str, Any]:
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(s[start : end + 1])


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    base = Path(req.path)
    result = ingest_folder_to_qdrant(base, reindex=req.reindex)
    return IngestResponse(**result)


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    hits = search_qdrant(req.question, req.top_k)
    context = build_context(hits)

    prompt = f"""
You are a local RAG assistant. You MUST return ONLY valid JSON.
No markdown. No explanations. No extra text.

Return JSON with this schema:
{{
  "answer": string,
  "confidence": number between 0 and 1,
  "notes": [string]
}}

Question:
{req.question}

Context (retrieved snippets):
{context}
""".strip()

    raw = (await generate(prompt)).strip()

    try:
        data = parse_llm_json(raw)
    except Exception:
        data = {"answer": "Nie udało się sparsować odpowiedzi LLM do JSON.", "confidence": 0.0, "notes": ["LLM output was not valid JSON."]}
    try:
        llm_json = LLMJson(**data)
    except Exception as e:
        llm_json = LLMJson(
            answer="Odpowiedź LLM nie pasuje do wymaganego schematu JSON.",
            confidence=0.0,
            notes=[f"Schema validation error: {repr(e)}"],
        )

    hits_sorted = sorted(hits, key=lambda x: float(x.get("score", 0)), reverse=True)

    sources: List[Source] = []
    seen = set()
    for h in hits_sorted:
        key = (str(h.get("file_path", "")), int(h.get("chunk_id", -1)))
        if key in seen:
            continue
        seen.add(key)

        sources.append(
            Source(
                file_path=str(h.get("file_path", "unknown")),
                chunk_id=int(h.get("chunk_id", -1)),
                score=float(h.get("score", 0.0)),
                excerpt=_clean_excerpt(str(h.get("excerpt", ""))),
            )
        )

    return AskResponse(
        answer=llm_json.answer,
        confidence=float(llm_json.confidence),
        sources=sources,
        notes=llm_json.notes,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
