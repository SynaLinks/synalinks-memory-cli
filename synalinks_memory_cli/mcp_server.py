# License Apache 2.0: (c) 2026 Yoan Sallami (Synalinks Team)

"""MCP server exposing the Synalinks Memory API as tools."""

from __future__ import annotations

import json
import sys
import time

import httpx
from mcp.server.fastmcp import FastMCP
from synalinks_memory import SynalinksError, SynalinksMemory

DEFAULT_BASE_URL = "https://app.synalinks.com/api"


def _wait_for_backend(base_url: str, timeout: float = 120.0) -> None:
    """Block until the backend health endpoint responds (cold-start warm-up).

    The health endpoint does not require an API key.  Retries every 2 seconds
    up to *timeout* seconds.  All output goes to stderr so it never interferes
    with the MCP stdio transport on stdout.
    """
    health_url = f"{base_url.rstrip('/')}/v1/health"
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = httpx.get(health_url, timeout=10.0)
            resp.raise_for_status()
            print("Backend is ready.", file=sys.stderr)
            return
        except Exception:
            if time.monotonic() >= deadline:
                print(
                    f"Warning: backend did not respond within {timeout}s "
                    "(tools will retry on first call).",
                    file=sys.stderr,
                )
                return
            if attempt == 1:
                print("Waiting for backend (cold start)...", file=sys.stderr)
            time.sleep(2)


def create_server(
    api_key: str | None,
    base_url: str | None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    """Build a FastMCP server wired to a SynalinksMemory client."""
    resolved_base_url = base_url or DEFAULT_BASE_URL

    # Wake up the backend before creating the client (no API key needed).
    _wait_for_backend(resolved_base_url)

    kwargs: dict = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    client = SynalinksMemory(**kwargs)
    mcp = FastMCP("synalinks-memory", host=host, port=port)

    @mcp.tool()
    def list_predicates() -> str:
        """List all tables, concepts, and rules in the knowledge base."""
        try:
            preds = client.list()
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        lines: list[str] = []
        for kind, items in [("table", preds.tables), ("concept", preds.concepts), ("rule", preds.rules)]:
            for item in items:
                desc = f" — {item.description}" if item.description else ""
                lines.append(f"[{kind}] {item.name}{desc}")
        return "\n".join(lines) if lines else "No predicates found."

    @mcp.tool()
    def execute(predicate: str, limit: int = 20, offset: int = 0) -> str:
        """Fetch rows from a table, concept, or rule.

        Args:
            predicate: Name of the table, concept, or rule to query.
            limit: Maximum number of rows to return (default 20).
            offset: Row offset for pagination (default 0).
        """
        try:
            result = client.execute(predicate, limit=limit, offset=offset)
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        return json.dumps(
            {
                "predicate": result.predicate,
                "columns": [c.name for c in result.columns],
                "rows": result.rows,
                "row_count": result.row_count,
                "total_rows": result.total_rows,
                "offset": result.offset,
            },
            default=str,
        )

    @mcp.tool()
    def search(predicate: str, keywords: str, limit: int = 20, offset: int = 0) -> str:
        """Search rows by keywords (fuzzy matching).

        Args:
            predicate: Name of the table, concept, or rule to search.
            keywords: Search terms for fuzzy matching.
            limit: Maximum number of rows to return (default 20).
            offset: Row offset for pagination (default 0).
        """
        try:
            result = client.search(predicate, keywords, limit=limit, offset=offset)
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        return json.dumps(
            {
                "predicate": result.predicate,
                "columns": [c.name for c in result.columns],
                "rows": result.rows,
                "row_count": result.row_count,
                "total_rows": result.total_rows,
                "offset": result.offset,
            },
            default=str,
        )

    @mcp.tool()
    def upload(file_path: str, name: str = "", description: str = "", overwrite: bool = False) -> str:
        """Upload a CSV or Parquet file as a new table.

        Args:
            file_path: Local path to a .csv or .parquet file.
            name: Optional predicate name (CamelCase). Derived from filename if empty.
            description: Optional table description.
            overwrite: Replace existing table with same name if True.
        """
        try:
            result = client.upload(
                file_path,
                name=name or None,
                description=description or None,
                overwrite=overwrite,
            )
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        return json.dumps(
            {
                "predicate": result.predicate,
                "columns": [c.name for c in result.columns],
                "row_count": result.row_count,
            },
        )

    @mcp.tool()
    def insert_row(predicate: str, row_json: str) -> str:
        """Insert a single row into a table.

        Args:
            predicate: Name of the table to insert into.
            row_json: JSON object mapping column names to values, e.g. '{"name": "Alice", "email": "alice@example.com"}'.
        """
        try:
            row = json.loads(row_json)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON — {exc}"

        if not isinstance(row, dict):
            return "Error: row_json must be a JSON object (not array or scalar)."

        try:
            result = client.insert(predicate, row)
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        return json.dumps(
            {"predicate": result.predicate, "row": result.row},
            default=str,
        )

    @mcp.tool()
    def update_rows(predicate: str, filter_json: str, values_json: str) -> str:
        """Update rows in a table that match a filter.

        Args:
            predicate: Name of the table to update.
            filter_json: JSON object of column→value conditions (ANDed), e.g. '{"name": "Alice"}'.
            values_json: JSON object of column→new value pairs, e.g. '{"email": "alice@new.com"}'.
        """
        try:
            filter_dict = json.loads(filter_json)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid filter JSON — {exc}"

        if not isinstance(filter_dict, dict):
            return "Error: filter_json must be a JSON object (not array or scalar)."

        try:
            values_dict = json.loads(values_json)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid values JSON — {exc}"

        if not isinstance(values_dict, dict):
            return "Error: values_json must be a JSON object (not array or scalar)."

        try:
            result = client.update(predicate, filter_dict, values_dict)
        except SynalinksError as exc:
            return f"Error: {exc.message}"

        return json.dumps(
            {
                "predicate": result.predicate,
                "updated_count": result.updated_count,
                "values": result.values,
            },
            default=str,
        )

    @mcp.tool()
    def chat(question: str) -> str:
        """Chat with the Synalinks agent about your data (multi-turn).

        Conversation history is maintained automatically across calls.
        Send "/clear" as the question to reset the conversation.

        Args:
            question: A natural-language question, or "/clear" to reset conversation history.
        """
        if question.strip() == "/clear":
            client.clear()
            return "Conversation history cleared."
        try:
            return client.chat(question)
        except SynalinksError as exc:
            return f"Error: {exc.message}"

    return mcp
