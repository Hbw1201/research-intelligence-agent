# Multi-Agent Intel

Multi-Agent Intel is an MVP scaffold for a personalized research intelligence system. It collects research updates, ranks them against user or group interests, generates Chinese digests with external LLM APIs, and pushes selected results to WeCom group robot webhooks.

## Architecture
Collectors gather source data from arXiv, PubMed, GitHub, and RSS. Services normalize, rank, summarize, record feedback, and push digests. MetaGPT orchestrates the multi-agent workflow, FastAPI exposes backend APIs, PostgreSQL stores structured records and vectors through pgvector, Redis supports cache and future task coordination, and APScheduler runs MVP scheduled jobs.

## Local Setup
```bash
cd multi-agent-intel
copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Docker Setup
```bash
cd multi-agent-intel
copy .env.example .env
docker compose up --build
```

## Healthcheck
```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"multi-agent-intel"}
```

## LLM Relay Configuration
The MVP uses an internal OpenAI-compatible chat completions relay. Configure it in `.env`:

```bash
LLM_PROVIDER=zyai
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=http://10.1.21.21:3000/v1
LLM_MODEL_CHEAP=glm-5.1
LLM_MODEL_STANDARD=glm-5.1
LLM_MODEL_STRONG=glm-5.1
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
LLM_MAX_TOKENS=8192
LLM_MAX_TOKENS_CHEAP=4096
LLM_MAX_TOKENS_STANDARD=8192
LLM_MAX_TOKENS_STRONG=16384
```

## Manual Daily Digest
Run a local collect-rank-digest pass without scheduler, web UI, or WeCom push:

```bash
python scripts/run_daily_digest.py --keywords "multi-agent systems,RAG" --sources arxiv,github --max-items 5 --output-path daily.md
```

Relative output paths are saved under `reports/`. Add `--rss-feed-url https://example.com/feed.xml` when `--sources` includes `rss`.

## Next Implementation Tasks
1. Add SQLAlchemy models and migrations.
2. Implement collectors with retry and rate limiting.
3. Implement the external LLM client and Chinese digest service.
4. Implement relevance ranking with keyword and vector similarity.
5. Implement scheduled workflows and WeCom push delivery.
