"""CLI entry point for fidelity-mcp.

Commands:
  fidelity-mcp login   — authenticate with Fidelity and cache the session
  fidelity-mcp serve   — start the MCP server (default when invoked by Claude)
  fidelity-mcp status  — check if the cached session is still valid
  fidelity-mcp logout  — clear the cached session
"""

from __future__ import annotations

import asyncio
import os

import click

from .auth import FidelitySession


@click.group()
def cli() -> None:
    """Fidelity MCP server for Claude."""


@cli.command()
@click.option("--username", envvar="FIDELITY_USERNAME", prompt="Fidelity username")
@click.option("--password", envvar="FIDELITY_PASSWORD", prompt="Fidelity password", hide_input=True)
@click.option("--totp-secret", envvar="FIDELITY_TOTP_SECRET", default=None, help="TOTP secret for automated 2FA")
def login(username: str, password: str, totp_secret: str | None) -> None:
    """Log in to Fidelity and save the session for MCP use."""
    session = FidelitySession()
    asyncio.run(session.login_interactive(username, password, totp_secret))
    click.echo("Login successful. You can now start the MCP server.")


@cli.command()
def status() -> None:
    """Check whether the cached Fidelity session is still valid."""
    session = FidelitySession()
    if not session.load():
        click.echo("No session found. Run `fidelity-mcp login` first.")
        raise SystemExit(1)
    if session.is_authenticated():
        click.echo("Session is valid.")
    else:
        click.echo("Session has expired. Run `fidelity-mcp login` to re-authenticate.")
        raise SystemExit(1)


@cli.command()
def logout() -> None:
    """Clear the cached Fidelity session."""
    session = FidelitySession()
    session.clear()
    click.echo("Session cleared.")


@cli.command()
def serve() -> None:
    """Start the MCP server (this is what Claude invokes)."""
    from .server import main

    main()


# Make `fidelity-mcp` with no subcommand start the server so Claude Desktop
# can invoke it simply as `fidelity-mcp` in its config.
@cli.result_callback()
def _default(*args: object, **kwargs: object) -> None:
    pass


cli.result_callback()(serve)

# Allow bare `fidelity-mcp` to default to `serve`
_original_main = cli.main


def _patched_main(*args: object, **kwargs: object) -> object:  # type: ignore[override]
    import sys

    if len(sys.argv) == 1:
        sys.argv.append("serve")
    return _original_main(*args, **kwargs)


cli.main = _patched_main  # type: ignore[method-assign]
