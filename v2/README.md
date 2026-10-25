# Admin PDF Toolkit v2

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design.

## Run

```bash
# server (Python 3.11+)
cd v2/server
pip install -e ".[dev]"
python -m adminpdf            # http://127.0.0.1:8000

# web UI (Node 20+) — build once, the server serves it
cd v2/web
npm ci
npm run build                 # outputs to server/adminpdf/web_dist
npm run dev                   # optional: hot-reload UI on :5173, proxies /api
```

LAN access: `APT_HOST=0.0.0.0 APT_LAN_ENABLED=true APT_PAIRING_KEY=<secret> python -m adminpdf`,
then open `http://<pc-ip>:8000/#pair=<secret>` on the phone.

## Check

```bash
cd v2/server && ruff check . && ruff format --check . && mypy adminpdf && pytest
cd v2/web && npm run check && npm run build
```
