# PLANS.md

## Phase 1: Project Scaffold
Status: TODO

Deliverables:
- FastAPI minimal app
- Docker Compose
- PostgreSQL
- Redis
- .env.example
- healthcheck endpoint
- basic project structure

Acceptance:
- `docker compose up -d` works
- `GET /health` returns OK

## Phase 2: Database Layer
Status: TODO

Deliverables:
- SQLAlchemy models
- users
- groups
- sources
- items
- item_scores
- feedback
- digests

Acceptance:
- database tables can be created
- unique URL/content hash constraints work

## Phase 3: Collectors
Status: TODO

Deliverables:
- arXiv collector
- PubMed collector
- GitHub collector
- RSS collector

Acceptance:
- each collector returns normalized ResearchItem objects
- collectors support keyword query, max_results, date range, retry, timeout

## Phase 4: LLM Client
Status: TODO

Deliverables:
- unified LLM client
- provider routing
- task-based model selection
- retry/fallback
- token/cost logging

Acceptance:
- screening, summarization, ranking prompts can call the configured provider

## Phase 5: Digest Service
Status: TODO

Deliverables:
- Chinese digest generation service
- structured digest item schema
- daily digest formatter
- safe fallback when LLM output is malformed

Acceptance:
- collected items can be summarized in Chinese
- malformed LLM output does not crash the workflow

## Phase 6: Ranking Service
Status: TODO

Deliverables:
- relevance scoring
- profile keyword matching
- pgvector similarity hooks
- item importance scoring

Acceptance:
- collected items can be ranked for a topic/profile
- ranking works without requiring manual sorting

## Phase 7: Lightweight Web Admin Dashboard
Status: TODO

Deliverables:
- FastAPI + Jinja2 server-rendered admin pages
- source management
- topic/profile management
- collected item browsing
- generated digest browsing
- manual collection trigger
- manual digest generation trigger
- manual WeCom push preview

Acceptance:
- an operator can review sources, topics, items, and digests from a browser
- an operator can manually trigger collection and digest generation
- an operator can preview the WeCom message before sending

Notes:
- Use FastAPI + Jinja2 templates for the MVP dashboard.
- Keep the UI simple and deployable on the same small lab server.
- React/Vite can be considered later as a richer future upgrade, but it is not part of the MVP dashboard.

## Phase 8: MetaGPT Agents
Status: TODO

Deliverables:
- ProfileAgent
- PaperAgent
- NewsAgent
- CodeAgent
- DatasetAgent
- RankerAgent
- DigestAgent
- CriticAgent

Acceptance:
- daily workflow can run on sample items

## Phase 9: WeCom Push
Status: TODO

Deliverables:
- weekly report service
- WeCom webhook push service

Acceptance:
- test message can be pushed to a group
- daily digest is formatted in Chinese markdown

## Phase 10: Feedback Loop
Status: TODO

Deliverables:
- feedback API
- feedback storage
- profile update logic

Acceptance:
- user feedback changes future ranking

## Phase 11: Source Discovery Agent
Status: FUTURE

Deliverables:
- SourceDiscoveryAgent
- website discovery recommendations
- RSS feed discovery recommendations
- GitHub repository/source recommendations
- human approval workflow before adding sources

Acceptance:
- candidate sources are recommended with rationale
- no new source is activated without human approval

## Phase 12: Deployment
Status: TODO

Deliverables:
- deploy script
- backup script
- logging
- healthcheck
- README deployment guide

Acceptance:
- system runs on lab server with Docker Compose
