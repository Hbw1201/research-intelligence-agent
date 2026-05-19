# Local SearxNG for Web Discovery

This directory provides a small self-hosted SearxNG option for the MVP web discovery layer. It is intended for local or lab-server use and binds to `127.0.0.1:8080` by default.

## Start

```bash
docker compose -f infra/searxng/docker-compose.yml up -d
```

## Windows Docker Proxy

If SearxNG engines are blocked or rate-limited from inside Docker on Windows, point the container at your host proxy before starting it:

```bash
SEARXNG_HTTP_PROXY=http://host.docker.internal:7897
SEARXNG_HTTPS_PROXY=http://host.docker.internal:7897
```

PowerShell example:

```powershell
$env:SEARXNG_HTTP_PROXY = "http://host.docker.internal:7897"
$env:SEARXNG_HTTPS_PROXY = "http://host.docker.internal:7897"
docker compose -f infra/searxng/docker-compose.yml up -d
```

## Test

Open this URL from the host machine:

```text
http://localhost:8080/search?q=single-cell+foundation+model&format=json
```

## Configure Multi-Agent Intel

Set these values in the main project `.env`:

```bash
WEB_SEARCH_PROVIDER=searxng
WEB_SEARCH_BASE_URL=http://localhost:8080
```

The SearxNG JSON API does not require an API key for this local MVP setup.

## Safety

Do not expose this SearxNG instance publicly without authentication, rate limiting, and a properly configured reverse proxy. The default compose file is intentionally local-only.
