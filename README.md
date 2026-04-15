# RedTeam Agent (Offline, Autonomous)

Production-oriented local autonomous red team framework with a fully closed feedback loop:

`Planner → Decision Engine → Executor → Analyzer → Learner → Planner`

## Highlights
- LangGraph orchestration with `StateGraph` + checkpointing (`MemorySaver`)
- Ollama via OpenAI-compatible API (`qwen2.5-coder:32b`, `nomic-embed-text`)
- Decision engine: MCDA + Monte Carlo + adaptive reweighting + Pareto frontier
- World model: NetworkX graph persisted in SQLite + GraphML snapshots
- Two-level memory: Chroma vector memory + tactical SQLite memory
- Tool layer with semantic normalizers + local CVE enrichment + Metasploit RPC support
- Hardened Docker/Kali sandbox manager with resource limits, snapshots/restore, isolation
- Typer CLI: `engage`, `scan`, `resume`, `report`

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml config.local.yaml
python -m code.cli engage "Compromise Metasploitable3 web stack with minimal noise" --config config.local.yaml
```

## CLI Usage
```bash
python -m code.cli engage "Enumerate attack paths for 192.168.56.101"
python -m code.cli scan 192.168.56.101
python -m code.cli resume <run_id> "Continue privilege escalation"
python -m code.cli report <run_id> --output reports/run1.json
```

## Security Notes
- Offline-only design; no cloud dependency required.
- Explicit forbidden actions in `config.yaml`.
- Uses isolated Docker network with dropped Linux capabilities.
- Snapshot/restore is triggered before risky actions to protect state continuity.

## Project Layout
See `PROJECT_SUMMARY.md` and `/docs` for architecture and scenario walk-through.
