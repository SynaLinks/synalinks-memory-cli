"""Synalinks Memory CLI — query your tables, concepts, and rules from the terminal."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from synalinks_memory import SynalinksError, SynalinksMemory

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


class _DefaultAskGroup(click.Group):
    """Custom group that treats unknown args as a question for the agent.

    This lets users type ``synalinks "my question"`` or even
    ``synalinks How are sales doing`` without any subcommand.
    """

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
        cmd_name = args[0] if args else None
        if cmd_name and cmd_name not in self.commands:
            # Not a known subcommand — route everything to the hidden _ask command
            return "_ask", self.commands["_ask"], args
        return super().resolve_command(ctx, args)


@click.group(cls=_DefaultAskGroup)
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
@click.option("--format", "-f", "fmt", default=None, type=click.Choice(["json", "csv", "parquet"]), help="Export as a file instead of a table.")
@click.option("--output", "-o", default=None, help="Output file path (defaults to <predicate>.<format>). Requires --format.")
@click.pass_context
def execute(ctx: click.Context, predicate: str, limit: int, offset: int, fmt: str | None, output: str | None) -> None:
    """Fetch rows from a table, concept, or rule.

    Without --format, prints a rich table. With --format, saves to a file.
    """
    if output and not fmt:
        err_console.print("[red]Error:[/red] --output requires --format (-f).")
        sys.exit(1)

    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])

    # --- File extract mode ---
    if fmt:
        if output is None:
            output = f"{predicate}.{fmt}"
        try:
            data = client.execute(predicate, format=fmt, limit=limit, offset=offset, output=output)
        except SynalinksError as exc:
            err_console.print(f"[red]Error:[/red] {exc.message}")
            sys.exit(1)
        finally:
            client.close()

        size_kb = len(data) / 1024
        console.print(f"[green]Saved[/green] {output} ({size_kb:.1f} KB)")
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
    for col in result.columns:
        table.add_column(col.name)
    for row in result.rows:
        table.add_row(*[_format_cell(row.get(col.name)) for col in result.columns])

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
    for col in result.columns:
        table.add_column(col.name)
    for row in result.rows:
        table.add_row(*[_format_cell(row.get(col.name)) for col in result.columns])

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
# synalinks "<question>"  (default — no subcommand needed)
# ---------------------------------------------------------------------------


@cli.command("_ask", hidden=True)
@click.argument("question", nargs=-1, required=True)
@click.pass_context
def _ask_cmd(ctx: click.Context, question: tuple[str, ...]) -> None:
    """Ask the Synalinks agent a question."""
    full_question = " ".join(question)
    client = _get_client(ctx.obj["api_key"], ctx.obj["base_url"])
    try:
        answer = client.ask(full_question)
    except SynalinksError as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        sys.exit(1)
    finally:
        client.close()

    from rich.markdown import Markdown
    console.print(Markdown(answer))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_cell(value: object) -> Text:
    """Format a cell value for display."""
    if value is None:
        return Text("null", style="dim italic")
    s = str(value)
    if len(s) > 80:
        s = s[:77] + "..."
    return Text(s)
