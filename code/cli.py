"""Typer CLI for local autonomous red team operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
import yaml
from rich import print

from .decision_engine import DecisionConfig, DecisionEngine
from .llm_client import LLMClient
from .memory import MemorySystem
from .models import MsfRpcConfig
from .orchestrator import RedTeamOrchestrator
from .tool_layer import ToolLayer
from .world_model import WorldModel

app = typer.Typer(help="Local Autonomous Red Team Agent")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def bootstrap(config_path: str):
    cfg = load_config(config_path)
    logging.basicConfig(level=getattr(logging, cfg["app"]["log_level"]))
    llm = LLMClient(
        base_url=cfg["llm"]["base_url"],
        api_key=cfg["llm"]["api_key"],
        model=cfg["llm"]["planning_model"],
        timeout_seconds=cfg["llm"]["timeout_seconds"],
        max_retries=cfg["llm"]["max_retries"],
    )
    decision = DecisionEngine(DecisionConfig(**cfg["decision_engine"]))
    memory = MemorySystem(
        chroma_path=cfg["memory"]["chroma_path"],
        sqlite_path=cfg["memory"]["tactical_sqlite_path"],
        collection_name=cfg["memory"]["collection_name"],
    )
    world = WorldModel(cfg["world_model"]["sqlite_path"])
    msf_cfg = MsfRpcConfig(**cfg["tools"]["metasploit_rpc"])
    tools = ToolLayer(timeout=cfg["docker"]["timeout_seconds"], metasploit_cfg=msf_cfg)
    orch = RedTeamOrchestrator(llm, decision, tools, memory, world, max_cycles=cfg["campaign"]["max_cycles"])
    return orch, cfg


@app.command("engage")
def engage(
    objective: str = typer.Option("Enumerate and validate attack path"),
    target: str = typer.Option("127.0.0.1"),
    config: str = typer.Option("config.yaml"),
    thread_id: str = typer.Option("session-default"),
):
    orch, _ = bootstrap(config)
    final_state = orch.run(objective, target, thread_id=thread_id)
    print(final_state.model_dump_json(indent=2))


@app.command("scan")
def scan(target: str = typer.Argument(...), config: str = typer.Option("config.yaml")):
    _, cfg = bootstrap(config)
    tools = ToolLayer(timeout=cfg["docker"]["timeout_seconds"])
    result = tools.run_nmap_scan(target=target, flags=cfg["tools"]["nmap_default_flags"])
    print(result.model_dump_json(indent=2))


@app.command("resume")
def resume(thread_id: str = typer.Argument(...), config: str = typer.Option("config.yaml")):
    orch, cfg = bootstrap(config)
    target = cfg["campaign"]["target_default"]
    final_state = orch.run("Resume previous campaign", target, thread_id=thread_id)
    print(final_state.model_dump_json(indent=2))


@app.command("report")
def report(output: str = typer.Option("report.json"), config: str = typer.Option("config.yaml")):
    _, cfg = bootstrap(config)
    world = WorldModel(cfg["world_model"]["sqlite_path"])
    report_payload = world.as_dict()
    Path(output).write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    print(f"[green]Report written:[/green] {output}")


if __name__ == "__main__":
    app()
