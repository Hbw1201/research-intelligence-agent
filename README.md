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

## Collector Proxy Configuration
External collectors may need an explicit proxy when Python's default environment proxy handling is unreliable. Configure one shared proxy for all collector traffic:

```bash
COLLECTOR_PROXY=http://127.0.0.1:7897
```

Or configure HTTP and HTTPS separately:

```bash
COLLECTOR_HTTP_PROXY=http://127.0.0.1:7897
COLLECTOR_HTTPS_PROXY=http://127.0.0.1:7897
```

On Windows PowerShell for the current terminal:

```powershell
$env:COLLECTOR_PROXY = "http://127.0.0.1:7897"
```

If your internal LLM relay is reachable directly, exclude it from system proxy handling as needed:

```powershell
$env:NO_PROXY = "10.1.21.21,localhost,127.0.0.1"
```

Collector request timeouts can be tuned with `COLLECTOR_TIMEOUT_SECONDS`, and arXiv can be overridden with `ARXIV_TIMEOUT_SECONDS`.

## Manual Daily Digest
Run a local collect-rank-digest pass without scheduler or web UI:

```bash
python scripts/run_daily_digest.py --keywords "multi-agent systems,RAG" --sources arxiv,github --max-items 5 --output-path daily.md
```

Relative output paths are saved under `reports/`. Add `--rss-feed-url https://example.com/feed.xml` when `--sources` includes `rss`.

To push the generated digest to a configured WeCom group robot, set `WECOM_WEBHOOK_URL` in `.env` and pass `--push-wecom` explicitly:

```bash
python scripts/run_daily_digest.py --keywords "multi-agent systems,RAG" --sources github --max-items 5 --push-wecom --wecom-title "今日科研情报"
```

To push an existing saved report:

```bash
python scripts/push_report_wecom.py --report-path reports/github_pubmed_wecom_test.md --message-type markdown --title "今日科研情报"
```

Long markdown reports are split into UTF-8 byte-sized chunks before delivery. Tune the per-message budget with `WECOM_MARKDOWN_MAX_BYTES` if your WeCom robot rejects oversized content.

## Next Implementation Tasks
1. Add SQLAlchemy models and migrations.
2. Implement collectors with retry and rate limiting.
3. Implement the external LLM client and Chinese digest service.
4. Implement relevance ranking with keyword and vector similarity.
5. Implement scheduled workflows and WeCom push delivery.
