# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A Python MCP server that connects Claude to Fidelity brokerage accounts. It exposes six tools: `get_accounts`, `get_positions`, `get_transactions`, `get_quote`, `preview_trade`, and `place_trade`.

Fidelity has no public API. The server uses the unofficial JSON APIs that Fidelity's own web app uses, accessed via session cookies obtained through a Playwright-based login flow.

## Commands

```bash
# Install (editable)
pip install -e ".[dev]"
playwright install chromium

# First-time auth (opens a headed browser)
fidelity-mcp login

# Check session validity
fidelity-mcp status

# Run the MCP server manually (Claude Desktop does this automatically)
fidelity-mcp serve

# Lint / type-check
ruff check src/
mypy src/

# Tests
pytest
pytest tests/test_client.py::test_get_accounts   # single test
```

## Architecture

```
src/fidelity_mcp/
├── cli.py        — Click CLI; bare `fidelity-mcp` defaults to `serve`
├── auth.py       — FidelitySession: cookie loading (env → cache → Playwright login)
├── client.py     — FidelityClient: thin httpx wrapper over Fidelity's unofficial endpoints
├── models.py     — Pydantic models (Account, Position, Transaction, Quote, OrderPreview, OrderResult)
└── server.py     — FastMCP server; tool definitions call FidelityClient methods
```

### Auth flow

`fidelity-mcp login` opens a headed Chromium window via Playwright, logs in (handling TOTP if `FIDELITY_TOTP_SECRET` is set), extracts cookies, and writes them to `~/.fidelity_mcp/session.json` (chmod 600). On every subsequent MCP tool call, `FidelitySession.load()` tries (1) `FIDELITY_SESSION_COOKIES` env var, (2) the cache file. If neither exists, the tool returns an instructive error string.

### Trading safety

`place_trade` requires `confirm=True`. The server instructions (baked into `FastMCP`) tell Claude to always call `preview_trade` first and present the result before setting `confirm=True`. Both tools validate `action ∈ {BUY, SELL}` and reject LIMIT orders missing `limit_price`.

### Unofficial API endpoints

| Purpose | URL |
|---|---|
| Accounts | `GET /ftgw/digital/portfolio/api/pls/accounts` |
| Positions | `GET /ftgw/digital/portfolio/api/pls/accounts/{acct}/positions` |
| Transactions | `GET /ftgw/digital/portfolio/api/pls/accounts/{acct}/activity` |
| Quote | `GET /ftgw/digital/trading/quoteBySymbol?symbol=X` |
| Preview order | `POST /ftgw/digital/trading/previewOrder` |
| Submit order | `POST /ftgw/digital/trading/submitOrder` |

These endpoints are not guaranteed stable. If a response shape changes, fix the parsing in `client.py` — the field-mapping comments there list the alternative key names Fidelity has used.

## Connecting to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fidelity": {
      "command": "fidelity-mcp",
      "env": {
        "FIDELITY_USERNAME": "your_username",
        "FIDELITY_PASSWORD": "your_password"
      }
    }
  }
}
```

Run `fidelity-mcp login` once before starting Claude Desktop. The cached session is reused automatically; re-run login when it expires.
