# License Apache 2.0: (c) 2026 Yoan Sallami (Synalinks Team)

"""Synalinks Memory CLI — query your tables, concepts, and rules from the terminal."""

from __future__ import annotations

import json
import os
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from synalinks_memory import ChatAnswerEvent, ChatStepEvent, SynalinksError, SynalinksMemory

console = Console()
err_console = Console(stderr=True)


def _get_client(api_key: str | None, base_url: str | None) -> SynalinksMemory:
    """Build a SynalinksMemory client from CLI options."""
    kwargs: dict = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    try:
        return SynalinksMemory(**kwargs)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)


class _DefaultChatGroup(click.Group):
    """Custom group that treats unknown args as a question for the agent.

    This lets users type ``synalinks "my question"`` or even
    ``synalinks How are sales doing`` without any subcommand.
    """

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
        cmd_name = args[0] if args else None
        if cmd_name and cmd_name not in self.commands:
            # Not a known subcommand — route everything to the hidden _chat command
            return "_chat", self.commands["_chat"], args
        return super().resolve_command(ctx, args)


@click.group(cls=_DefaultChatGroup)
@click.option("--api-key", envvar="SYNALINKS_API_KEY", default=None, help="API key (or set SYNALINKS_API_KEY).")
@click.option("--base-url", default=None, help="Override API base URL.")
@click.pass_context
def cli(ctx: click.Context, api_key: str | None, base_url: str | None) -> None:
    """Synalinks Memory — query your data from the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["base_url"] = base_url


# ---------------------------------------------------------------------------
# synalinks list
# ---------------------------------------------------------------------------


@cli.command("list")
@click.pass_context
def list_predicates(ctx: click.Context) -> None:
    """List all tables, concepts, and rules."""
    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        preds = client.list()
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    table = Table(title="Predicates")
    table.add_column("Type", style="bold cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Description")

    for t in preds.tables:
        table.add_row("table", t.name, t.description)
    for c in preds.concepts:
        table.add_row("concept", c.name, c.description)
    for r in preds.rules:
        table.add_row("rule", r.name, r.description)

    if table.row_count == 0:
        console.print("[dim]No predicates found.[/dim]")
    else:
        console.print(table)


# ---------------------------------------------------------------------------
# synalinks query <predicate>
# ---------------------------------------------------------------------------


@cli.command("execute")
@click.argument("predicate")
@click.option("--limit", "-n", default=20, show_default=True, help="Max rows to return.")
@click.option("--offset", default=0, show_default=True, help="Row offset for pagination.")
@click.option("--format", "-f", "fmt", default=None, type=click.Choice(["json", "csv", "parquet"]), help="Output format (prints to stdout unless -o is given).")
@click.option("--output", "-o", default=None, help="Save to file instead of stdout. Requires --format.")
@click.pass_context
def execute(ctx: click.Context, predicate: str, limit: int, offset: int, fmt: str | None, output: str | None) -> None:
    """Fetch rows from a table, concept, or rule.

    Without --format, prints a rich table. With --format, outputs formatted
    data to stdout (pipeable). Use -o to save to a file instead.
    """
    if output and not fmt:
        err_console.print("[red]Error:[/red] --output requires --format (-f).")
        sys.exit(1)

    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])

    # --- File export mode (--format with --output) ---
    if fmt and output:
        try:
            written = client.execute(predicate, format=fmt, limit=limit, offset=offset, output=output)
        except SynalinksError as exc:
            err_console.print(f"[red]Error:[/red] {exc.message}")
            sys.exit(1)
        finally:
            client.close()

        size_kb = written / 1024
        console.print(f"[green]Saved[/green] {output} ({size_kb:.1f} KB)")
        return

    # --- Formatted stdout mode (--format without --output, pipeable) ---
    if fmt:
        try:
            data = client.execute(predicate, format=fmt, limit=limit, offset=offset)
        except SynalinksError as exc:
            err_console.print(f"[red]Error:[/red] {exc.message}")
            sys.exit(1)
        finally:
            client.close()

        sys.stdout.buffer.write(data)
        return

    # --- Default table display ---
    try:
        result = client.execute(predicate, limit=limit, offset=offset)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    if not result.rows:
        console.print(f"[dim]No rows in {predicate}.[/dim]")
        return

    table = Table(
        title=f"{predicate}",
        caption=f"Showing {result.row_count} of {result.total_rows} rows (offset {result.offset})",
    )
    col_names = [col.name for col in result.columns]
    for name in col_names:
        table.add_column(name)
    for row in result.rows:
        table.add_row(*[_format_cell(row.get(name)) for name in col_names])

    console.print(table)


# ---------------------------------------------------------------------------
# synalinks search <predicate> <keywords>
# ---------------------------------------------------------------------------


@cli.command("search")
@click.argument("predicate")
@click.argument("keywords")
@click.option("--limit", "-n", default=20, show_default=True, help="Max rows to return.")
@click.option("--offset", default=0, show_default=True, help="Row offset for pagination.")
@click.pass_context
def search(ctx: click.Context, predicate: str, keywords: str, limit: int, offset: int) -> None:
    """Search rows by keywords (fuzzy matching)."""
    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        result = client.search(predicate, keywords, limit=limit, offset=offset)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    if not result.rows:
        console.print(f'[dim]No results for "{keywords}" in {predicate}.[/dim]')
        return

    table = Table(
        title=f'Search "{keywords}" in {predicate}',
        caption=f"Showing {result.row_count} of {result.total_rows} rows",
    )
    col_names = [col.name for col in result.columns]
    for name in col_names:
        table.add_column(name)
    for row in result.rows:
        table.add_row(*[_format_cell(row.get(name)) for name in col_names])

    console.print(table)


# ---------------------------------------------------------------------------
# synalinks add <file>
# ---------------------------------------------------------------------------


@cli.command("add")
@click.argument("file", type=click.Path(exists=True))
@click.option("--name", default=None, help="Predicate name (CamelCase). Derived from filename if omitted.")
@click.option("--description", default=None, help="Table description.")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing table with same name.")
@click.pass_context
def upload(ctx: click.Context, file: str, name: str | None, description: str | None, overwrite: bool) -> None:
    """Upload a CSV or Parquet file as a new table."""
    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        result = client.upload(file, name=name, description=description, overwrite=overwrite)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    table = Table(title="Upload Result")
    table.add_column("Predicate", style="bold cyan")
    table.add_column("Columns", style="bold")
    table.add_column("Rows", justify="right")

    col_names = ", ".join(c.name for c in result.columns) if result.columns else "-"
    table.add_row(result.predicate, col_names, str(result.row_count))
    console.print(table)


# ---------------------------------------------------------------------------
# synalinks insert <predicate> <json>
# ---------------------------------------------------------------------------


@cli.command("insert")
@click.argument("predicate")
@click.argument("row_json")
@click.pass_context
def insert(ctx: click.Context, predicate: str, row_json: str) -> None:
    """Insert a single row into a table.

    ROW_JSON is a JSON object mapping column names to values, e.g.
    '{"name": "Alice", "email": "alice@example.com"}'
    """
    import json

    try:
        row = json.loads(row_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid JSON: {exc}")
        sys.exit(1)

    if not isinstance(row, dict):
        err_console.print("[red]Error:[/red] ROW_JSON must be a JSON object (not array or scalar).")
        sys.exit(1)

    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        result = client.insert(predicate, row)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    table = Table(title=f"Inserted into {result.predicate}")
    table.add_column("Column", style="bold cyan")
    table.add_column("Value")
    for col_name, value in result.row.items():
        table.add_row(col_name, str(value) if value is not None else "null")
    console.print(table)


# ---------------------------------------------------------------------------
# synalinks update <predicate> <filter_json> <values_json>
# ---------------------------------------------------------------------------


@cli.command("update")
@click.argument("predicate")
@click.argument("filter_json")
@click.argument("values_json")
@click.pass_context
def update(ctx: click.Context, predicate: str, filter_json: str, values_json: str) -> None:
    """Update rows in a table that match a filter.

    FILTER_JSON is a JSON object of column→value conditions (ANDed), e.g.
    '{"name": "Alice"}'

    VALUES_JSON is a JSON object of column→new value pairs, e.g.
    '{"email": "alice@new.com"}'
    """
    import json

    try:
        filter_dict = json.loads(filter_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid filter JSON: {exc}")
        sys.exit(1)

    if not isinstance(filter_dict, dict):
        err_console.print("[red]Error:[/red] FILTER_JSON must be a JSON object.")
        sys.exit(1)

    try:
        values_dict = json.loads(values_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid values JSON: {exc}")
        sys.exit(1)

    if not isinstance(values_dict, dict):
        err_console.print("[red]Error:[/red] VALUES_JSON must be a JSON object.")
        sys.exit(1)

    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        result = client.update(predicate, filter_dict, values_dict)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    console.print(f"[green]Updated {result.updated_count} row(s)[/green] in {result.predicate}")
    table = Table(title="Values set")
    table.add_column("Column", style="bold cyan")
    table.add_column("Value")
    for col_name, value in result.values.items():
        table.add_row(col_name, str(value) if value is not None else "null")
    console.print(table)


# ---------------------------------------------------------------------------
# synalinks "<question>"  (default — no subcommand needed)
# ---------------------------------------------------------------------------


def _history_path() -> str:
    """Resolve the path to the persistent chat history file."""
    base = os.environ.get("SYNALINKS_HOME", os.path.expanduser("~/.synalinks"))
    if not os.access(os.path.dirname(base) or os.path.expanduser("~"), os.W_OK):
        base = os.path.join("/tmp", ".synalinks")
    return os.path.join(base, "chat_history.json")


@cli.command("_chat", hidden=True)
@click.argument("question", nargs=-1, required=True)
@click.pass_context
def _chat_cmd(ctx: click.Context, question: tuple[str, ...]) -> None:
    """Ask the Synalinks agent a question."""
    full_question = " ".join(question)
    history_file = _history_path()

    # Handle /clear command
    if full_question.strip() == "/clear":
        try:
            os.remove(history_file)
        except FileNotFoundError:
            pass
        console.print("[green]Conversation cleared.[/green]")
        return

    # Load previous conversation history
    messages: list[dict] = []
    try:
        with open(history_file) as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    client._messages = messages
    try:
        answer = ""
        with console.status("[bold cyan]Thinking...", spinner="dots") as status:
            for event in client.chat_stream(full_question):
                if isinstance(event, ChatStepEvent):
                    status.update(f"[bold cyan]{event.label}")
                elif isinstance(event, ChatAnswerEvent):
                    answer = event.answer
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        # Save updated conversation history
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, "w") as f:
            json.dump(client._messages, f)
        client.close()

    from rich.markdown import Markdown
    console.print(Markdown(answer))


# ---------------------------------------------------------------------------
# synalinks serve  (MCP server)
# ---------------------------------------------------------------------------


@cli.command("serve")
@click.option(
    "--transport",
    "-t",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    default="stdio",
    show_default=True,
    help="MCP transport protocol.",
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to (sse / streamable-http).")
@click.option("--port", "-p", default=8000, show_default=True, help="Port to bind to (sse / streamable-http).")
@click.pass_context
def serve(ctx: click.Context, transport: str, host: str, port: int) -> None:
    """Start an MCP server for AI assistants."""
    from synalinks_memory_cli.mcp_server import create_server

    server = create_server(ctx.obj["api_key"], ctx.obj["base_url"], host=host, port=port)
    if transport == "stdio":
        err_console.print("[bold cyan]Synalinks Memory MCP server (stdio)[/bold cyan]")
    else:
        err_console.print(f"[bold cyan]Synalinks Memory MCP server ({transport}) → http://{host}:{port}[/bold cyan]")
    server.run(transport=transport)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_NULL = Text("null", style="dim italic")


def _format_cell(value: object) -> str | Text:
    """Format a cell value for display."""
    if value is None:
        return _NULL
    s = str(value)
    if len(s) > 80:
        return s[:77] + "..."
    return s
