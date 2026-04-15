"""Typer-based CLI for local autonomous red-team operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from orchestrator import RedTeamOrchestrator

app = typer.Typer(help="Offline autonomous red-team agent")
console = Console()
logging.basicConfig(level=logging.INFO)


def _orchestrator(config: str) -> RedTeamOrchestrator:
    return RedTeamOrchestrator(config_path=config)


@app.command()
def engage(objective: str, config: str = typer.Option("config.yaml", "--config")) -> None:
    """Run full autonomous engagement loop."""
    orch = _orchestrator(config)
    result = orch.run(objective=objective)
    console.print(f"[green]Run complete:[/green] {result.run_id}")
    console.print(f"Actions executed: {len(result.history)}")


@app.command()
def scan(target: str, config: str = typer.Option("config.yaml", "--config")) -> None:
    """Run focused scan objective."""
    objective = f"Enumerate and prioritize vulnerabilities on {target}"
    engage(objective=objective, config=config)


@app.command()
def resume(run_id: str, objective: str, config: str = typer.Option("config.yaml", "--config")) -> None:
    """Resume a previous run by thread id."""
    orch = _orchestrator(config)
    result = orch.run(objective=objective, thread_id=run_id)
    console.print(f"[cyan]Resumed run:[/cyan] {result.run_id}, actions={len(result.history)}")


@app.command()
def report(run_id: str, output: str = typer.Option("reports/latest_report.json", "--output")) -> None:
    """Generate a simple report from tactical memory placeholder records."""
    report_path = Path(output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "status": "report_generated", "note": "Extend with full aggregation pipeline."}
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print(f"[yellow]Report written:[/yellow] {report_path}")


if __name__ == "__main__":
    app()
