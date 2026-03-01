# relay-proxy-service

Skeleton Python service that accepts HTTP and WebSocket requests and proxies them to one of the upstreams from environment configuration.

## Requirements
- Python 3.11+

## Setup
1. Create `.env` from `.env.example` and adjust `UPSTREAMS` (and `WS_UPSTREAMS` if needed).
   - Use `PROTOCOLS=http,ws` to control which protocols are enabled.
2. Install dependencies.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run
```bash
source .venv/bin/activate
uvicorn relay_proxy_service.main:app --host 0.0.0.0 --port 8080 --reload
```

## Routes
- HTTP: `/{path}` (all methods)
- WebSocket: `/{path}`
- Metrics: `/metrics`
- Liveness: `/livez`
- Readiness: `/readyz`
- Health summary: `/healthz`

## Health checks
`/livez` is always OK if the process is running. `/readyz` turns to 503 if there was no successful proxied HTTP request in the last `HEALTH_WINDOW_SECONDS` (default 60s), and also checks that enabled protocols have upstreams configured. `/healthz` returns a summary.

## Notes
- Hop-by-hop headers are filtered.
- WebSocket proxying is basic; add auth, timeouts, and better error handling as needed.

## Real upstream example (Polygon Amoy)
Configure `.env` to use real upstreams:
```
UPSTREAMS=https://polygon-amoy.api.onfinality.io/rpc?apikey=YOUR_API_KEY,https://polygon-amoy.drpc.org
WS_UPSTREAMS=
UPSTREAM_STRATEGY=random
```

If an upstream includes a path (like `/rpc`), call the proxy root `/` so it maps to that base path.

Example request through the proxy:
```bash
curl --request POST \
  --url http://localhost:8080/ \
  --header 'content-type: application/json' \
  --data '{
  "jsonrpc": "2.0",
  "method": "eth_blockNumber",
  "params": [],
  "id": 1
}'
```
