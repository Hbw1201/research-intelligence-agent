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

## Phase 5: MetaGPT Agents
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

## Phase 6: Digest and Push
Status: TODO

Deliverables:
- daily digest service
- weekly report service
- WeCom webhook push service

Acceptance:
- test message can be pushed to a group
- daily digest is formatted in Chinese markdown

## Phase 7: Feedback Loop
Status: TODO

Deliverables:
- feedback API
- feedback storage
- profile update logic

Acceptance:
- user feedback changes future ranking

## Phase 8: Deployment
Status: TODO

Deliverables:
- deploy script
- backup script
- logging
- healthcheck
- README deployment guide

Acceptance:
- system runs on lab server with Docker Compose