# crypto-proxy-service

Skeleton Python service that accepts HTTP and WebSocket requests and proxies them to one of the upstreams from environment configuration.

## Requirements
- Python 3.11+

## Setup
1. Create `.env` from `.env.example` and adjust `UPSTREAMS`.
2. Install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run
```bash
uvicorn crypto_proxy_service.main:app --host 0.0.0.0 --port 8080 --reload
```

## Routes
- HTTP: `/{path}` (all methods)
- WebSocket: `/ws/{path}`

## Notes
- Hop-by-hop headers are filtered.
- WebSocket proxying is basic; add auth, timeouts, and better error handling as needed.
