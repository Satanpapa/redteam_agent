"""Typer CLI for offline autonomous red team agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich import print

from .orchestrator import RedTeamOrchestrator

app = typer.Typer(help="Local autonomous red team agent")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


@app.command("engage")
def engage(
    objective: str = typer.Option(..., help="Engagement objective"),
    scope: str = typer.Option(..., help="Target scope (CIDR/host list)"),
    max_iterations: int = typer.Option(5, help="Maximum feedback iterations"),
    config: str = typer.Option("config.yaml", help="Config file path"),
) -> None:
    """Run full autonomous loop: planner→decision→executor→analyzer→learner."""
    _setup_logging()
    orchestrator = RedTeamOrchestrator(config)
    final_state = orchestrator.run(objective=objective, scope=scope, max_iterations=max_iterations)

    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{final_state.run_id}.json"
    out_file.write_text(final_state.model_dump_json(indent=2), encoding="utf-8")

    print(f"[green]Run completed.[/green] run_id={final_state.run_id} report={out_file}")


@app.command("scan")
def scan(
    target: str = typer.Argument(..., help="Target host"),
    config: str = typer.Option("config.yaml", help="Config file"),
) -> None:
    """Run a quick single-iteration reconnaissance workflow."""
    _setup_logging()
    orchestrator = RedTeamOrchestrator(config)
    state = orchestrator.run(objective="Quick recon", scope=target, max_iterations=1)
    print(json.dumps({"run_id": state.run_id, "summary": state.analysis.model_dump() if state.analysis else {}}, indent=2))


@app.command("resume")
def resume(run_id: str = typer.Argument(..., help="Run id to resume")) -> None:
    """Resume command placeholder for checkpoint-backed recovery flows."""
    print(f"[yellow]Resume requested for {run_id}. Use LangGraph checkpointer backend to recover historical state.[/yellow]")


@app.command("report")
def report(path: str = typer.Argument(..., help="Path to report JSON")) -> None:
    """Render an existing JSON report in terminal."""
    report_path = Path(path)
    if not report_path.exists():
        raise typer.BadParameter(f"Report not found: {path}")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    print("[bold]Report[/bold]")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    app()
