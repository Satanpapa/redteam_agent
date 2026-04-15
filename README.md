# Red Team Agent
## Полностью локальный автономный адаптивный Red Team Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.x-green.svg)](https://github.com/langchain-ai/langgraph)
[![Docker](https://img.shields.io/badge/Docker-Required-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Обзор

Red Team Agent — это интеллектуальная система автоматизации red team операций, построенная на принципах **истинного автономного агента** с обратной связью и динамическим принятием решений. В отличие от линейных пайплайнов, данная система использует замкнутый цикл обучения: каждая итерация улучшает будущие решения.

### Ключевые особенности

- **Полностью локальный**: Работает offline с Ollama (без внешних API)
- **Адаптивный Decision Engine**: MCDA + Monte Carlo для выбора оптимальных действий
- **World Model**: Граф знаний (NetworkX + SQLite) для структурированного представления сети
- **Умный Tool Layer**: Структурированный вывод в Pydantic модели + обогащение CVE данных
- **Двухуровневая память**: Vector Store (Chroma/LanceDB) + SQLite для тактик
- **Безопасное выполнение**: Docker sandbox с Kali Linux

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│                    CLI / Configuration                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER (LangGraph)                    │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐         │
│  │ Planner │ → │ Decision│ → │Executor │ → │ Analyzer│         │
│  │  Agent  │   │ Engine  │   │  Agent  │   │  Agent  │         │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘         │
│       ↑                                         │               │
│       └────────────── Learner ←─────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   WORLD MODEL   │ │  MEMORY SYSTEM  │ │ DOCKER SANDBOX  │
│  (NetworkX +    │ │ (Chroma/LanceDB │ │  (Kali Linux)   │
│   SQLite)       │ │  + SQLite)      │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Execution Flow

```
Planner → Decision Engine → Executor → Analyzer → Learner
    ↑                                              │
    └────────────── should_continue? ←─────────────┘
```

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Language | Python 3.11+ |
| Orchestration | LangGraph (StateGraph + Checkpointing) |
| LLM | Ollama (qwen2.5-coder:32b / deepseek-coder-v2) |
| Data Models | Pydantic v2 |
| Graph DB | NetworkX + SQLite |
| Vector Store | ChromaDB / LanceDB |
| Sandbox | Docker + Kali Linux |

---

## Установка

### Предварительные требования

- Python 3.11+
- Docker + Docker Compose
- Ollama (для локальных LLM)

### Шаги установки

```bash
# 1. Клонирование репозитория
git clone https://github.com/your-org/redteam-agent.git
cd redteam-agent

# 2. Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Настройка Ollama
ollama pull qwen2.5-coder:32b
ollama pull nomic-embed-text

# 5. Запуск
python -m redteam_agent --config config.yaml
```

### Docker Setup

```bash
# Build sandbox image
docker build -t redteam-sandbox -f containers/Dockerfile .

# Run with docker-compose
docker-compose up -d
```

---

## Конфигурация

### Пример config.yaml

```yaml
# LLM Configuration
llm:
  provider: ollama
  base_url: http://localhost:11434
  model: qwen2.5-coder:32b
  temperature: 0.7
  max_tokens: 4096
  embedding_model: nomic-embed-text

# Docker Sandbox
docker:
  image: kalilinux/kali-rolling:latest
  cpu_limit: 2.0
  memory_limit: 4g
  network_mode: bridge
  capabilities:
    - NET_ADMIN

# Decision Engine
decision:
  enable_monte_carlo: true
  monte_carlo_iterations: 100
  weights:
    probability: 0.25
    impact: 0.25
    cost: 0.20
    risk: 0.15
    novelty: 0.10
    stealth: 0.05

# Agent Behavior
agent:
  max_iterations: 100
  parallel_actions: 1
  require_confirmation: false

# Database
database:
  sqlite_path: ./data/redteam.db
  vector_store_type: chroma
  vector_store_path: ./data/vectors
```

---

## Использование

### Базовый запуск

```python
from redteam_agent import RedTeamAgent
from models import AgentConfig

# Load configuration
config = AgentConfig.from_yaml("config.yaml")

# Create agent
agent = RedTeamAgent(config)

# Define scope
scope = ["192.168.56.0/24"]
exclusions = ["192.168.56.1"]

# Run engagement
result = agent.run(
    target_scope=scope,
    excluded_targets=exclusions,
    max_iterations=50
)

# Generate report
report = agent.generate_report()
report.save("engagement_report.pdf")
```

### CLI Interface

```bash
# Quick scan
redteam-agent scan 192.168.1.0/24

# Full engagement
redteam-agent engage --scope targets.txt --config config.yaml

# Resume from checkpoint
redteam-agent resume --checkpoint checkpoint.pkl

# Generate report
redteam-agent report --session-id <uuid> --format pdf
```

---

## Структура проекта

```
redteam_agent/
├── code/
│   ├── __init__.py
│   ├── models.py              # Pydantic data models
│   ├── decision_engine.py     # MCDA + Monte Carlo
│   ├── tool_layer.py          # Tool normalizers
│   ├── docker_sandbox.py      # Sandbox manager
│   ├── orchestrator.py        # LangGraph StateGraph
│   ├── world_model.py         # Graph knowledge base
│   ├── memory.py              # Two-tier memory
│   └── llm_client.py          # Ollama integration
├── containers/
│   ├── Dockerfile             # Kali Linux sandbox
│   └── docker-compose.yml
├── docs/
│   ├── ARCHITECTURE.md        # Detailed architecture
│   ├── ATTACK_SCENARIO.md     # Example scenarios
│   └── FUTURE_ENHANCEMENTS.md # Roadmap
├── tests/
│   └── test_*.py
├── config.yaml
├── requirements.txt
└── README.md
```

---

## Decision Engine

### 4-мерная метрика оценки

| Метрика | Диапазон | Описание |
|---------|----------|----------|
| Probability of Success | 0.0 - 1.0 | Вероятность успеха |
| Impact / Value | 0 - 10 | Потенциальная ценность |
| Cost | 0 - 10 | Временные и ресурсные затраты |
| Risk | 0 - 10 | Риск обнаружения |

### Scoring Formula

```python
score = (prob_success * impact) / (cost * (1 + risk))
```

### Monte Carlo Simulation

```python
# Run N iterations with parameter variations
for _ in range(mc_iterations):
    sampled_params = sample_from_distribution(base_params)
    scores.append(calculate_score(sampled_params))

final_score = mean(scores)
confidence_interval = (mean - 1.96*std, mean + 1.96*std)
```

---

## World Model

### Структура графа

```
Host → Port → Service → Vulnerability → Exploit
  ↓       ↓
Network Credentials
```

### Сущности

- **Host**: IP, hostname, OS, статус компрометации
- **Port**: number, protocol, state, service
- **Service**: name, version, CPE, баннер
- **Vulnerability**: CVE, severity, CVSS
- **Exploit**: module, success_rate
- **Credential**: username, password, hash

### Запросы

```python
# Get compromised hosts
compromised = world_model.get_compromised_hosts()

# Find attack paths
paths = world_model.get_attack_paths("192.168.1.1", "192.168.1.10")

# High-value targets
hvt = world_model.identify_high_value_targets(top_n=5)
```

---

## Tool Layer

### Поддерживаемые инструменты

| Инструмент | Нормализатор | Выходные данные |
|------------|--------------|-----------------|
| nmap | XML/JSON parser | Hosts, Ports, Services, OS |
| gobuster | Text parser | URLs, Directories |
| sqlmap | JSON parser | SQLi vulnerabilities |
| hydra | Text parser | Valid credentials |
| nuclei | JSON parser | CVEs, vulnerabilities |

### Пример нормализации

```python
from tool_layer import get_tool_registry

# Get normalizer
registry = get_tool_registry()

# Process output
result = registry.process("nmap", tool_output)

# Result contains structured entities
hosts = result["hosts"]      # List[Host]
ports = result["ports"]      # List[Port]
vulns = result["vulnerabilities"]  # List[Vulnerability]
```

---

## Безопасность

### Принципы

1. **Изоляция**: Все инструменты выполняются только в Docker
2. **Resource Limits**: CPU, memory, network ограничения
3. **No Host Access**: Нет прямого доступа к host-системе
4. **Audit Logging**: Все действия логируются

### Sandbox Features

- Snapshot/restore для чистого состояния
- Network isolation
- Volume mounting control
- Capability restrictions

---

## Сравнение с Decepticon

| Фича | Decepticon | Red Team Agent |
|------|------------|----------------|
| Локальность | Требует API ключи | Полностью offline |
| Decision Engine | Жёсткие правила | MCDA + Monte Carlo |
| World Model | Плоские структуры | Граф знаний |
| Tool Output | Regex parsing | Pydantic модели |
| Memory | Отсутствует | Vector + Tactical |
| Обучение | Нет | Адаптивные веса |

---

## Roadmap

### P0 (Критический)
- [ ] RL-based Decision Engine
- [ ] Multi-Agent System
- [ ] Advanced LLM Integration

### P1 (Высокий)
- [ ] Distributed Architecture
- [ ] GPU Acceleration
- [ ] Advanced Evasion

### P2 (Средний)
- [ ] SIEM Integration
- [ ] MITRE ATT&CK Mapping
- [ ] Automated Reporting

---

## Лицензия

MIT License - см. [LICENSE](LICENSE)

**Важное замечание**: Этот инструмент предназначен только для:
- Авторизованного тестирования на проникновение
- Исследований в области безопасности
- Образовательных целей

Использование против систем без явного разрешения является незаконным.

---

## Контакты

- Issues: [GitHub Issues](https://github.com/Satanpapa/redteam_agent/issues)
- Discussions: [GitHub Discussions](https://github.com/Satanpapa/redteam-agent/discussions)

---

## Благодарности

- [LangGraph](https://github.com/langchain-ai/langgraph) - Orchestration framework
- [Ollama](https://ollama.ai) - Local LLM inference
- [Decepticon](https://github.com/PurpleAILAB/Decepticon) - Inspiration and best practices
