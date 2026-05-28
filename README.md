# fidelity-mcp

An MCP server that connects Claude to your Fidelity brokerage account.

## What Claude can do

| Tool | Description |
|---|---|
| `get_accounts` | List all accounts with balances |
| `get_positions` | Current holdings for an account |
| `get_transactions` | Trade and activity history |
| `get_quote` | Real-time stock/ETF quote |
| `preview_trade` | Estimate cost and commission before trading |
| `place_trade` | Execute a real order (requires explicit confirmation) |

## Setup

### 1. Install

```bash
git clone https://github.com/sriram-mv/upgraded-octo-enigma
cd upgraded-octo-enigma
pip install -e .
playwright install chromium
```

### 2. Log in to Fidelity

```bash
fidelity-mcp login
```

A Chromium browser window opens. Log in normally (including 2FA). The session is saved to `~/.fidelity_mcp/session.json`.

**Automated 2FA**: If your account uses a TOTP authenticator app, export your secret and set `FIDELITY_TOTP_SECRET=<base32_secret>` — the login step will fill in the code automatically.

### 3. Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "fidelity": {
      "command": "fidelity-mcp"
    }
  }
}
```

Restart Claude Desktop. You should see "fidelity" in the MCP servers list.

## Session management

Sessions expire periodically (typically after a few hours of inactivity). Re-run `fidelity-mcp login` when tools return a "Session expired" error. Check status any time with:

```bash
fidelity-mcp status
```

## Environment variables

| Variable | Purpose |
|---|---|
| `FIDELITY_USERNAME` | Used by `fidelity-mcp login` if not prompted |
| `FIDELITY_PASSWORD` | Used by `fidelity-mcp login` if not prompted |
| `FIDELITY_TOTP_SECRET` | Base32 TOTP secret for automated 2FA |
| `FIDELITY_SESSION_COOKIES` | JSON dict of cookies (alternative to file-based cache) |

## Disclaimer

This project uses Fidelity's unofficial internal API. It is not affiliated with or endorsed by Fidelity Investments. Use at your own risk. Trading tools execute real orders with real money — always review `preview_trade` output before confirming.
