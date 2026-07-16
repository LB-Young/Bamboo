"""CLI commands for Bamboo Knowledge Network packages."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bamboo.bkn.export import BKNExportFormat, export_bkn
from bamboo.bkn.loader import load_bkn_definition
from bamboo.bkn.registry import create_bkn_registry
from bamboo.bkn.retrieval import render_bkn_results
from bamboo.bkn.store import BKNStore
from bamboo.bkn.validator import BKNValidationError

app = typer.Typer(help="Manage and debug Bamboo Knowledge Networks.", no_args_is_help=True)
console = Console()


@app.command("list")
def list_bkn(include_inactive: bool = typer.Option(False, "--all", help="Show inactive BKN packages")) -> None:
    """List discovered BKN packages."""
    registry = create_bkn_registry()
    definitions = registry.list(include_inactive=include_inactive)
    errors = registry.errors()
    if not definitions and not errors:
        console.print("[yellow]No BKN packages found.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("network", no_wrap=True)
    table.add_column("status", no_wrap=True)
    table.add_column("nodes", justify="right")
    table.add_column("relations", justify="right")
    table.add_column("root")
    for definition in definitions:
        status = definition.manifest.status if definition.manifest is not None else ("active" if definition.enabled else "inactive")
        table.add_row(
            definition.name,
            status,
            str(len(definition.entities)),
            str(len(definition.relations)),
            str(definition.root),
        )
    console.print(table)
    _print_errors(errors)


@app.command("validate")
def validate_bkn(target: str = typer.Argument("", help="Network name, platform id, or local BKN directory")) -> None:
    """Validate discovered BKN packages or one target."""
    if target:
        _validate_one_target(target)
        return
    registry = create_bkn_registry()
    definitions = registry.list(include_inactive=True)
    errors = registry.errors()
    for definition in definitions:
        console.print(f"[green]ok[/green] {definition.name} {definition.root}")
    _print_errors(errors)
    if errors:
        raise typer.Exit(1)


@app.command("index")
def index_bkn(target: str = typer.Argument("", help="Network name, platform id, or local BKN directory")) -> None:
    """Refresh BKN indexes."""
    if target:
        _validate_one_target(target, indexed=True)
        return
    registry = create_bkn_registry()
    registry.refresh()
    summary = registry.summary()
    for name in summary["active_networks"]:
        console.print(f"[green]indexed[/green] {name}")
    _print_errors(summary["errors"])
    if summary["errors"]:
        raise typer.Exit(1)


@app.command("search")
def search_bkn(
    query: str = typer.Argument(..., help="Search query"),
    network: str = typer.Option("auto", "--network", "-n", help="Network name or auto"),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum result count"),
    max_hops: int = typer.Option(2, "--max-hops", help="Relationship expansion depth"),
) -> None:
    """Search active BKN packages."""
    registry = create_bkn_registry()
    bounded_limit = max(1, min(int(limit), 20))
    bounded_hops = max(0, min(int(max_hops), 5))
    matches = registry.search(query, network=network, limit=bounded_limit, max_hops=bounded_hops)
    console.print(render_bkn_results(query=query, network=network, matches=matches))


@app.command("export")
def export_bkn_command(
    network: str = typer.Argument(..., help="Network name or platform id to export"),
    format: str = typer.Option("mermaid", "--format", "-f", help="mermaid, dot, or markdown"),
    node: str = typer.Option("", "--node", help="Optional node id for neighborhood export"),
    depth: int = typer.Option(1, "--depth", help="Neighborhood depth when --node is set"),
) -> None:
    """Export a BKN graph or node neighborhood."""
    registry = create_bkn_registry()
    definition = registry.get(network)
    if definition is None:
        raise typer.BadParameter(f"BKN network not found: {network}")
    output_format = _parse_format(format)
    if output_format is None:
        raise typer.BadParameter("format must be mermaid, dot, or markdown")
    console.print(export_bkn(definition, output_format=output_format, node=node, depth=max(0, min(int(depth), 5))))


def _validate_one_target(target: str, *, indexed: bool = False) -> None:
    path = Path(target).expanduser()
    if path.exists():
        try:
            definition = load_bkn_definition(path)
        except BKNValidationError as exc:
            console.print(f"[red]error[/red] {exc}")
            raise typer.Exit(1) from exc
        console.print(f"[green]{'indexed' if indexed else 'ok'}[/green] {definition.name} {definition.root}")
        if indexed:
            store = BKNStore()
            store.ensure()
            store.write_index(definition)
        return
    registry = create_bkn_registry()
    definition = registry.get(target)
    errors = registry.errors()
    if definition is None:
        _print_errors(errors)
        raise typer.BadParameter(f"BKN network not found: {target}")
    console.print(f"[green]{'indexed' if indexed else 'ok'}[/green] {definition.name} {definition.root}")


def _print_errors(errors: dict[str, str]) -> None:
    for root, error in sorted(errors.items()):
        console.print(f"[red]error[/red] {root}: {error}")


def _parse_format(value: str) -> BKNExportFormat | None:
    normalized = value.strip().lower()
    if normalized in {"mermaid", "dot", "markdown"}:
        return normalized  # type: ignore[return-value]
    return None
