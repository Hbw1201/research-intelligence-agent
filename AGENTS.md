# AGENTS.md

## Project Name
Multi-Agent Research Intelligence System

## Goal
Build a personalized multi-agent intelligence system for research and technical updates. The system collects papers, methods, code repositories, datasets, news, and field developments, then analyzes, ranks, summarizes, and pushes personalized digests to WeCom / WeChat groups.

## MVP Scope
The MVP should include:
- arXiv collector
- PubMed collector
- GitHub collector
- RSS collector
- user and group profiles
- source management
- deduplication
- LLM-based relevance screening
- LLM-based Chinese summarization
- personalized ranking
- daily digest generation
- weekly report generation
- WeCom group webhook push
- feedback API

## Out of Scope for MVP
Do not implement:
- personal WeChat login
- unofficial WeChat protocol
- local LLM inference
- complex frontend
- full PDF deep reading for all papers
- large-scale knowledge graph
- multi-tenant billing
- production-grade permission system

## Tech Stack
- Python 3.10 or 3.11
- FastAPI
- PostgreSQL + pgvector
- Redis
- MetaGPT
- SQLAlchemy
- Pydantic Settings
- APScheduler or Celery
- Docker Compose
- External LLM APIs
- WeCom group robot webhook

## Coding Rules
1. Do not hard-code secrets.
2. Read all secrets from environment variables.
3. Keep modules small and testable.
4. Add type hints for public functions.
5. Add logging for external API calls.
6. Add retry and timeout for network calls.
7. Add unit tests for collectors and services.
8. Do not silently swallow exceptions.
9. Prefer simple, readable code over over-engineering.
10. Keep the system deployable on a small lab server.

## Agent Design
Use MetaGPT for workflow orchestration.

Required roles:
- ProfileAgent: manages user/group interests.
- CollectorAgent: coordinates data collection.
- PaperAgent: analyzes papers.
- NewsAgent: analyzes news.
- CodeAgent: analyzes GitHub repositories.
- DatasetAgent: analyzes datasets.
- RankerAgent: scores relevance and importance.
- DigestAgent: creates Chinese digests.
- CriticAgent: checks factuality and output quality.

## Daily Workflow
collect -> normalize -> deduplicate -> store -> analyze -> rank -> digest -> push -> record feedback

## Output Language
User-facing summaries should be Chinese by default.
Internal code, comments, and documentation may use English.