"""spedas-agent-kit — unified SPEDAS-oriented MCP facade over CDAWeb, PDS, and SPICE backends."""

__version__ = "0.1.0"


def main() -> None:
    """Console entry point for the SPEDAS Agent Kit server."""
    try:
        from spedas_agent_kit.server import serve
    except ImportError as exc:
        from spedas_agent_kit.installation import install_hint

        print(
            "Error: SPEDAS Agent Kit server requires the MCP extra.\n"
            f"{install_hint('mcp')}"
        )
        raise SystemExit(1) from exc
    serve()
