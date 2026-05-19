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

Digest runs use a lightweight JSONL seen-item store to avoid repeating papers, GitHub repositories, and web pages across runs. By default, the CLI filters fingerprints already recorded in `data/seen_items.jsonl`:

```bash
SEEN_ITEM_STORE_PATH=data/seen_items.jsonl
FILTER_SEEN_ITEMS=true
```

When a report is generated successfully, included items are marked as seen. When `--push-wecom` succeeds, those same items are also recorded as pushed. The fingerprint priority is DOI, PubMed ID, arXiv ID, GitHub repository identity, canonical URL, then normalized title fallback. Tracking parameters such as `utm_*`, `fbclid`, `gclid`, `ref`, `source`, and `campaign` are stripped before URL fingerprints are computed.

To rerun a report while deliberately keeping previously seen items, pass `--include-seen`:

```bash
python scripts/run_daily_digest.py --keywords "multi-agent systems,RAG" --sources arxiv,github --max-items 5 --include-seen
```

To use a different history file for testing or a specific group:

```bash
python scripts/run_daily_digest.py --keywords "single-cell" --sources github,pubmed --seen-store-path data/single_cell_seen_items.jsonl
```

If every collected item has already been seen, the report states `No new items after deduplication.` and the CLI skips WeCom delivery unless `--include-seen` is explicitly set.

## Source Registry
Phase 8C adds a lightweight JSON source registry for trusted or blocked discovery targets. It stores source candidates in `data/source_registry.json` without database migrations:

```bash
SOURCE_REGISTRY_PATH=data/source_registry.json
SOURCE_REGISTRY_ENABLED=true
SOURCE_REGISTRY_AUTO_UPDATE=false
```

Manage sources manually with:

```bash
python scripts/manage_sources.py list
python scripts/manage_sources.py add --name "Nature Single Cell" --url "https://www.nature.com/subjects/single-cell-analysis" --source-type website --tags single-cell,nature
python scripts/manage_sources.py disable https://www.nature.com/subjects/single-cell-analysis
python scripts/manage_sources.py block-domain reddit.com
python scripts/manage_sources.py export
```

The registry can import useful web-discovery candidates such as datasets, benchmarks, news, blogs, lab pages, company research pages, and discovered RSS/Atom feed URLs. It does not fetch every RSS candidate or crawl registered sites in this phase.

To update the registry during a manual digest run, opt in explicitly:

```bash
python scripts/run_daily_digest.py --keywords "single-cell foundation model" --sources web,github --max-items 5 --update-source-registry
```

When enabled, the report includes a `Source registry updates` section with new sources added, existing sources updated, and blocked domains skipped. Normal digest ranking, summarization, seen-item filtering, and WeCom behavior are unchanged.

To push the generated digest to a configured WeCom group robot, set `WECOM_WEBHOOK_URL` in `.env` and pass `--push-wecom` explicitly:

```bash
python scripts/run_daily_digest.py --keywords "multi-agent systems,RAG" --sources github --max-items 5 --push-wecom --wecom-title "今日科研情报"
```

If your network requires an explicit proxy for WeCom delivery, configure one of:

```bash
WECOM_PROXY=http://127.0.0.1:7897
WECOM_HTTP_PROXY=http://127.0.0.1:7897
WECOM_HTTPS_PROXY=http://127.0.0.1:7897
```

`WECOM_PROXY` takes precedence and disables environment proxy inheritance for WeCom HTTP calls. Web discovery page body fetching is disabled by default for stable MVP runs:

```bash
WEB_DISCOVERY_FETCH_PAGES=false
```

To push an existing saved report:

```bash
python scripts/push_report_wecom.py --report-path reports/github_pubmed_wecom_test.md --message-type markdown --title "今日科研情报"
```

Long markdown reports are split into UTF-8 byte-sized chunks before delivery. Tune the per-message budget with `WECOM_MARKDOWN_MAX_BYTES` if your WeCom robot rejects oversized content.

## Static HTML Reports
Daily digest runs can also write a static HTML report under `reports/site/`. The generated page is mobile-friendly, self-contained, and uses embedded CSS without external JavaScript:

```bash
REPORT_SITE_DIR=reports/site
REPORT_PUBLIC_BASE_URL=
REPORT_PUSH_LINK_ONLY=false
REPORT_LINK_THRESHOLD_ITEMS=8
```

Generate HTML alongside the markdown report:

```bash
python scripts/run_daily_digest.py --keywords "single-cell foundation model" --sources web,github --max-items 8 --html-report
```

This writes a timestamped file such as `reports/site/daily_20260519_0830.html` and updates `reports/site/latest.html`.

For local MVP serving, FastAPI exposes the report directory at `/reports`:

```bash
uvicorn backend.main:app --reload
```

Then open:

```text
http://localhost:8000/reports/latest.html
```

To share the report link in WeCom, configure a base URL that points at the same report directory:

```bash
REPORT_PUBLIC_BASE_URL=https://your-internal-host/reports
```

Then push only a short WeCom summary plus the latest report link:

```bash
python scripts/run_daily_digest.py --keywords "single-cell foundation model" --sources web,github --max-items 8 --html-report --push-wecom --push-link-only
```

The link-only message includes `今日科研情报已更新`, the item count, the top three titles, and `阅读全文：{REPORT_PUBLIC_BASE_URL}/latest.html`. If `REPORT_PUBLIC_BASE_URL` is empty, the CLI still saves the HTML report and prints the local path, but it skips link-only WeCom delivery because the link would not be public. For production, serve `reports/site` through nginx or an internal network route rather than relying on the development FastAPI static mount.

## AI + Bioinformatics Hotspot Topics
Phase 8E adds a lightweight topic registry for AI + bioinformatics hotspot discovery. It starts with bilingual seed topics such as `AI for biology`, `bioinformatics foundation model`, `single-cell foundation model`, `perturbation prediction`, `drug response`, `virtual cell`, `spatial transcriptomics`, `生信 大模型`, `单细胞 基础模型`, `扰动预测`, `药物反应`, and `空间转录组`.

Configure the registry in `.env`:

```bash
TOPIC_REGISTRY_PATH=data/topic_registry.json
HOTSPOT_DISCOVERY_ENABLED=true
HOTSPOT_MAX_TOPICS=50
HOTSPOT_MIN_SCORE=0.2
```

Manage topics manually:

```bash
python scripts/manage_topics.py list
python scripts/manage_topics.py add --topic "cell atlas foundation model" --aliases "cell atlas FM" --score 0.7
python scripts/manage_topics.py disable "cell atlas foundation model"
python scripts/manage_topics.py export
```

When hotspot discovery is enabled, the web query planner can use enabled registry topics above `HOTSPOT_MIN_SCORE` as additional bounded search queries. This remains a search-planning aid only; it does not add a scheduler, web UI, crawler, or MetaGPT workflow.

## Broad Web Discovery with SearxNG
The `web` source uses a self-hosted SearxNG JSON endpoint and stays deliberately bounded: it plans a small set of search queries, collects only search results, optionally fetches individual pages when `WEB_DISCOVERY_FETCH_PAGES=true`, and does not run an unrestricted crawler.

Query expansion is enabled by default so one research topic can fan out into broader source categories such as news, blogs, datasets, benchmarks, lab pages, company research pages, and technical updates:

```bash
WEB_DISCOVERY_QUERY_EXPANSION=true
WEB_DISCOVERY_QUERY_CATEGORIES=general,news,blog,dataset,benchmark,lab,company_research
WEB_DISCOVERY_RESULTS_PER_QUERY=5
WEB_DISCOVERY_TOTAL_MAX_RESULTS=30
```

For example, a topic like `single-cell foundation model perturbation prediction drug response` can produce searches for the base topic plus variants with `benchmark`, `dataset`, `blog`, `news`, lab/news wording, and research-page wording. Results from planned queries are merged and deduplicated by normalized URL and title before they enter ranking and digest generation.

Tune `WEB_DISCOVERY_QUERY_CATEGORIES` to control coverage. Use a smaller set such as `general,dataset,benchmark` for dataset-heavy monitoring, or add `code,preprint,method` when you want more repositories, preprints, and method pages. The collector still respects `WEB_DISCOVERY_RESULTS_PER_QUERY`, `WEB_DISCOVERY_TOTAL_MAX_RESULTS`, domain allow/block lists, and the CLI `--max-items` budget.

## Next Implementation Tasks
1. Add SQLAlchemy models and migrations.
2. Implement collectors with retry and rate limiting.
3. Implement the external LLM client and Chinese digest service.
4. Implement relevance ranking with keyword and vector similarity.
5. Implement scheduled workflows and WeCom push delivery.
