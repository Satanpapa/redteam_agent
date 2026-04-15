# redteam_agent

Локальный автономный Red Team Agent нового поколения (offline-first), построенный на:
- Python 3.11+
- LangGraph (StateGraph + MemorySaver)
- Ollama через OpenAI-compatible API (`qwen2.5-coder:32b`, `nomic-embed-text`)
- Docker + Kali Linux
- Pydantic v2, NetworkX, SQLite, ChromaDB

## Основные возможности

- Замкнутый автономный цикл:
  `Planner → Decision Engine → Executor → Analyzer → Learner → Planner`
- World Model как граф активов/связей (NetworkX + SQLite persistence)
- Decision Engine: MCDA + Monte Carlo + Pareto frontier + adaptive weights
- Tool Layer: нормализаторы + DataEnricher (локальная CVE логика) + Metasploit RPC
- Memory system: Tactical SQLite + Vector ChromaDB
- Docker Sandbox Manager: lifecycle, limits, snapshots/restore, network/volume policy
- Удобный Typer CLI: `engage`, `scan`, `resume`, `report`

## Структура

```text
redteam_agent/
├── README.md
├── PROJECT_SUMMARY.md
├── requirements.txt
├── config.yaml
├── code/
├── containers/
├── docs/
└── tests/
```

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Убедись, что Ollama и Docker запущены локально.

```bash
python -m code.cli engage --objective "Initial foothold" --scope "192.168.56.0/24" --max-iterations 3
```

## CLI

```bash
python -m code.cli engage --objective "Domain compromise simulation" --scope "10.10.10.0/24"
python -m code.cli scan 192.168.56.101
python -m code.cli resume <run_id>
python -m code.cli report reports/<run_id>.json
```

## Конфигурирование

Все настройки в `config.yaml`:
- LLM/Ollama endpoints
- tuning decision engine
- Docker sandbox constraints
- memory backends
- metasploit RPC параметры

## Безопасность

- По умолчанию network isolation для контейнера: `none`
- Drop Linux capabilities + `no-new-privileges`
- Snapshot перед опасными действиями для rollback

## Тесты

```bash
pytest -q
```

## Отказ от ответственности

Использовать только на системах, где у вас есть явное разрешение на тестирование.
