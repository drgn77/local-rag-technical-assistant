## Local Technical RAG Assistant (Offline)

A local Retrieval-Augmented Generation (RAG) assistant designed for analyzing and consulting technical system documentation.
The application works fully offline, communicates exclusively via JSON, and runs inside Docker on Linux (via WSL2 on Windows).

## Project Goal

The goal of this project is to build a local technical assistant that:

analyzes technical documentation (JSON, Markdown, TXT)

stores knowledge in a Qdrant vector database

answers user questions using a local LLM (Ollama)

communicates only through JSON

works fully offline

runs in a Dockerized environment

## RAG flow:

Documents are loaded and split into chunks

Text chunks are embedded and stored in Qdrant

User question is embedded and matched against stored vectors

Relevant context is built from top-k results

Local LLM (Ollama) generates a JSON-only response based on the context

##  Docker & Environment

The application runs using Docker Compose and consists of three services:

rag_app – FastAPI backend (RAG logic)

qdrant – vector database

ollama – local LLM runtime

## Indexing Documentation (/ingest)

The /ingest endpoint loads and indexes documentation files.

Example request:
{
  "path": "/data",
  "reindex": true
}

## Setup / Configuration (WSL2, Docker)

This project is designed to be executed on Ubuntu running in WSL2 and uses a shared Docker network and persistent volumes to avoid conflicts between multiple projects.

1. Clone the repository

Clone the project inside the Linux filesystem (recommended):
~~~bash
git clone https://github.com/drgn77/local-rag-technical-assistant.git
cd local-rag-technical-assistant
~~~

The repository should be located in /home/<user>/... and not under /mnt/c.

2. Create shared Docker network

The application uses a common external Docker network required by the evaluation environment:
~~~bash
docker network create ai_stack
~~~

If the network already exists, Docker will return a warning — this is expected.

Qdrant (named volume)

Qdrant stores its vector data in a named Docker volume:

qdrant_data → /qdrant/storage


This volume is created automatically by Docker Compose.

3. Prepare volumes
Create the directory:
~~~ 
mkdir -p volumes/ollama
~~~

This directory is mounted as:
~~~
./volumes/ollama → /root/.ollama
~~~
4.Start the containers

Build and run the project:
~~~ bash
docker compose up -d --build
~~~

Verify that all required services are running:
~~~
docker ps
~~~

Expected containers:

ollama

qdrant

rag_app

5.Download the LLM model (first run only)

On first execution, the language model must be downloaded:
~~~ git 
docker exec -it ollama ollama pull qwen2.5:3b
~~~

Verify:
~~~ 
docker exec -it ollama ollama list
~~~

6.Download the LLM model (first run only)

On first execution, the language model must be downloaded:
~~~ 
docker exec -it ollama ollama pull qwen2.5:3b
~~~

Verify:
~~~ 
docker exec -it ollama ollama list
~~~

 
## Asking Questions (/ask)

The /ask endpoint allows querying the indexed documentation.

Example request:
{
  "question": "What is the primary DNS?",
  "top_k": 5
}

Example response:
{
  "answer": "The primary DNS is 1.1.1.1.",
  "confidence": 0.92,
  "sources": [
    {
      "file_path": "config.json",
      "chunk_id": 0,
      "score": 0.87,
      "excerpt": "Primary DNS is set to 1.1.1.1."
    }
  ]
}

## JSON-Only Communication

All endpoints accept and return JSON only

The LLM is strictly instructed to return valid JSON

Responses are validated using Pydantic

Fallback JSON is returned if the model output is invalid

## Offline Mode

The LLM model is downloaded once

No external APIs are used

After setup, the application works without internet access

## Summary
Summary

This project demonstrates a fully local, offline RAG system for technical documentation analysis.
It combines modern vector search, local LLM inference, and containerized deployment while ensuring
strict JSON-based communication.

## Screenshoots
![Swagger UI](assets/swagger.png)
![Ingest](assets/ingest.png)
![Ask](assets/ask_1.png)
![Ask](assets/ask_2.png)
![Docker](assets/docker_ps.png)
![Offline](assets/offline.png)
