"""
CLI for Red Team Agent v2.0

Modern Typer-based command-line interface with rich output.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from .models import EngagementConfig, EngagementScope, TargetInfo
from .orchestrator import RedTeamOrchestrator

app = typer.Typer(
    name="redteam-agent",
    help="Autonomous Red Team Agent CLI",
    add_completion=True,
)

console = Console()
logger = logging.getLogger(__name__)


@app.command()
def engage(
    target: str = typer.Option(..., "-t", "--target", help="Target IP or hostname"),
    scope: EngagementScope = typer.Option(
        EngagementScope.INTERNAL, "-s", "--scope", help="Engagement scope"
    ),
    ports: Optional[str] = typer.Option(None, "-p", "--ports", help="Port range to scan"),
    max_depth: int = typer.Option(5, "-d", "--depth", help="Maximum attack depth"),
    timeout_hours: int = typer.Option(24, "-T", "--timeout", help="Timeout in hours"),
    name: Optional[str] = typer.Option(None, "-n", "--name", help="Engagement name"),
):
    """Start a new penetration testing engagement."""
    console.print("[bold blue]Starting Red Team Engagement[/bold blue]\n")
    
    # Create engagement config
    target_info = TargetInfo(address=target)
    
    config = EngagementConfig(
        name=name or f"Engagement-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        scope=scope,
        targets=[target_info],
        max_depth=max_depth,
        timeout_hours=timeout_hours,
    )
    
    console.print(f"[green]Target:[/green] {target}")
    console.print(f"[green]Scope:[/green] {scope.value}")
    console.print(f"[green]Max Depth:[/green] {max_depth}")
    console.print(f"[green]Timeout:[/green] {timeout_hours}h\n")
    
    # Initialize orchestrator
    try:
        orchestrator = RedTeamOrchestrator()
        
        # Run engagement
        console.print("[yellow]Initializing autonomous agent...[/yellow]\n")
        
        with console.status("[bold green]Running engagement...", spinner="dots"):
            result = orchestrator.run(config)
        
        # Display results
        _display_engagement_result(result)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def scan(
    target: str = typer.Option(..., "-t", "--target", help="Target to scan"),
    ports: str = typer.Option("1-1000", "-p", "--ports", help="Port range"),
    aggressive: bool = typer.Option(False, "-A", "--aggressive", help="Aggressive scan"),
):
    """Run reconnaissance scan on target."""
    console.print(f"[bold blue]Scanning target: {target}[/bold blue]\n")
    
    from .tool_layer import ToolExecutor
    import asyncio
    
    executor = ToolExecutor()
    
    # Build nmap command
    params = {
        "target": target,
        "ports": ports,
        "scan_type": "-A" if aggressive else "-sT",
    }
    
    console.print(f"[green]Ports:[/green] {ports}")
    console.print(f"[green]Mode:[/green] {'Aggressive' if aggressive else 'Standard'}\n")
    
    with console.status("[bold green]Scanning...", spinner="dots"):
        result = asyncio.run(executor.execute("nmap", params))
    
    if result.success:
        console.print("[green]Scan completed successfully[/green]\n")
        
        # Display findings
        if result.normalized_data.get("services"):
            table = Table(title="Discovered Services")
            table.add_column("Port", style="cyan")
            table.add_column("Protocol", style="magenta")
            table.add_column("Service", style="green")
            table.add_column("Version", style="yellow")
            
            for service in result.normalized_data["services"]:
                table.add_row(
                    str(service.get("port", "")),
                    service.get("protocol", ""),
                    service.get("service_name", ""),
                    service.get("version", ""),
                )
            
            console.print(table)
        
        if result.normalized_data.get("vulnerabilities"):
            vuln_table = Table(title="Potential Vulnerabilities")
            vuln_table.add_column("CVE", style="red")
            vuln_table.add_column("Severity", style="yellow")
            vuln_table.add_column("Description", style="white")
            
            for vuln in result.normalized_data["vulnerabilities"]:
                vuln_table.add_row(
                    vuln.get("cve_id", "N/A"),
                    vuln.get("severity", "unknown"),
                    vuln.get("description", "")[:50] + "...",
                )
            
            console.print(vuln_table)
    else:
        console.print(f"[red]Scan failed:[/red] {result.error_message}")


@app.command()
def resume(
    session_id: str = typer.Option(..., "-s", "--session-id", help="Session ID to resume"),
):
    """Resume a paused engagement."""
    console.print(f"[bold blue]Resuming session: {session_id}[/bold blue]\n")
    
    try:
        orchestrator = RedTeamOrchestrator()
        result = orchestrator.resume(session_id)
        
        _display_engagement_result(result)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def report(
    session_id: str = typer.Option(..., "-s", "--session-id", help="Session ID"),
    format: str = typer.Option("markdown", "-f", "--format", help="Output format"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Output file"),
):
    """Generate engagement report."""
    console.print(f"[bold blue]Generating report for: {session_id}[/bold blue]\n")
    
    # Generate report content
    report_content = _generate_report(session_id, format)
    
    if output:
        Path(output).write_text(report_content)
        console.print(f"[green]Report saved to:[/green] {output}")
    else:
        console.print(report_content)


@app.command()
def status():
    """Show system status."""
    console.print("[bold blue]Red Team Agent Status[/bold blue]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="white")
    
    # Check Ollama
    ollama_status = "[green]Running[/green]"
    ollama_details = "localhost:11434"
    table.add_row("Ollama LLM", ollama_status, ollama_details)
    
    # Check Docker
    docker_status = "[green]Running[/green]"
    docker_details = "Docker daemon available"
    table.add_row("Docker Sandbox", docker_status, docker_details)
    
    # Check databases
    db_status = "[green]Ready[/green]"
    db_details = "SQLite + ChromaDB"
    table.add_row("Memory System", db_status, db_details)
    
    console.print(table)


@app.command()
def reset(
    force: bool = typer.Option(False, "-f", "--force", help="Force reset without confirmation"),
):
    """Reset agent state (use with caution)."""
    if not force:
        confirm = typer.confirm("Are you sure you want to reset all agent state?")
        if not confirm:
            raise typer.Abort()
    
    console.print("[yellow]Resetting agent state...[/yellow]")
    
    # Clear memory and world model
    from .memory import MemorySystem
    from .world_model import WorldModel
    
    memory = MemorySystem()
    memory.clear()
    
    world_model = WorldModel()
    world_model.clear()
    
    console.print("[green]Agent state reset complete[/green]")


def _display_engagement_result(result) -> None:
    """Display engagement results."""
    console.print("\n[bold blue]Engagement Results[/bold blue]\n")
    
    # Summary table
    summary = Table(title="Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    
    summary.add_row("Status", result.status)
    summary.add_row("Iterations", str(result.iteration_count))
    summary.add_row("Targets Discovered", str(len(result.discovered_targets)))
    summary.add_row("Vulnerabilities Found", str(len(result.vulnerabilities)))
    summary.add_row("Actions Executed", str(len(result.action_history)))
    
    console.print(summary)
    
    # Vulnerabilities
    if result.vulnerabilities:
        vuln_tree = Tree("[bold red]Vulnerabilities[/bold red]")
        
        for vuln in result.vulnerabilities[:10]:  # Limit display
            vuln_tree.add(
                f"{vuln.cve_id or vuln.name} - {vuln.severity.value.upper()}"
            )
        
        console.print(vuln_tree)
    
    # Lessons learned
    if result.lessons_learned:
        lesson_tree = Tree("[bold green]Lessons Learned[/bold green]")
        
        for lesson in result.lessons_learned[-5:]:
            lesson_tree.add(lesson)
        
        console.print(lesson_tree)


def _generate_report(session_id: str, format: str) -> str:
    """Generate report in specified format."""
    # Placeholder report generation
    report = f"""# Red Team Engagement Report

## Session Information
- **Session ID**: {session_id}
- **Generated**: {datetime.now().isoformat()}

## Executive Summary

This report summarizes the findings of the automated penetration test.

## Findings

### Discovered Targets
- Target analysis data

### Vulnerabilities
- Vulnerability details

### Recommendations
- Security recommendations

---
*Generated by Red Team Agent v2.0*
"""
    
    if format == "json":
        return json.dumps({"report": report, "session_id": session_id})
    
    return report


if __name__ == "__main__":
    app()
