# Red Team Agent (Offline, Autonomous, LangGraph)

Локальный автономный red-team агент нового поколения для controlled security testing в изолированной среде.

## Ключевые возможности

- Полный feedback loop: Planner → Decision Engine → Executor → Analyzer → Learner.
- World Model: граф атакуемой среды (NetworkX + SQLite).
- Decision Engine: MCDA + Monte Carlo + Pareto + adaptive weights.
- Память: ChromaDB (semantic) + SQLite (tactical).
- Tool Layer: интеллектуальная нормализация + CVE enrichment + Metasploit RPC.
- Docker sandbox на Kali Linux с ограничениями ресурсов, snapshot/restore, network isolation.
- Полностью offline-first архитектура (кроме локального доступа к Docker daemon и Ollama).

## Быстрый старт

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Запуск кампании:

```bash
python -m code.cli engage --objective "Enumerate attack path" --target "192.168.56.101"
```

Сканирование:

```bash
python -m code.cli scan 192.168.56.101
```

Возобновление:

```bash
python -m code.cli resume session-default
```

Генерация отчета:

```bash
python -m code.cli report --output report.json
```

## Структура

- `code/` — core modules
- `containers/` — Dockerfile + compose
- `docs/` — архитектура, сценарий, roadmap
- `tests/` — unit tests

## Безопасность

Используйте только в авторизованных лабораториях (например, Metasploitable 3). Проект предназначен для defensive security validation и red team exercise automation.
