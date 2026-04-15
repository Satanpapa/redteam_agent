# Autonomous Red Team Agent v2.0

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 Overview

A fully autonomous, offline-capable Red Team Agent powered by local LLMs (Ollama + Qwen2.5-Coder). This agent performs intelligent penetration testing with a complete feedback loop, world model, and adaptive decision-making.

## ✨ Key Features

- **🧠 Autonomous Operation**: Complete closed feedback loop (Planner → Decision Engine → Executor → Analyzer → Learner → Planner)
- **🌍 World Model**: NetworkX-based graph with SQLite persistence for tracking targets, vulnerabilities, and attack paths
- **🎲 Advanced Decision Making**: MCDA + Monte Carlo simulation + Pareto frontier analysis
- **🔧 Smart Tool Layer**: Intelligent normalizers, DataEnricher with CVE logic, Metasploit RPC support
- **🐳 Docker Sandbox**: Isolated Kali Linux environment with snapshot/restore, resource limits, network isolation
- **💾 Two-Level Memory**: Vector Store (ChromaDB) + Tactical SQLite for short-term and long-term memory
- **📡 Offline First**: Works completely offline with local LLMs and databases

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Red Team Agent v2.0                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Planner    │────▶│  Decision    │────▶│   Executor   │    │
│  │    Node      │     │   Engine     │     │   (Tools)    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         ▲                                         │            │
│         │                                         ▼            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Learner    │◀────│   Analyzer   │◀────│   Analyzer   │    │
│  │    Node      │     │    Node      │     │    Node      │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                    Core Components                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ World Model  │  │ Memory System│  │ Docker Sandbox│          │
│  │ (NetworkX)   │  │ (Chroma+SQLite)│ │ (Kali Linux) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                    Local LLM Layer                              │
│              Ollama (qwen2.5-coder:32b)                         │
│              Embeddings (nomic-embed-text)                      │
└─────────────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed diagrams.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Ollama with models:
  ```bash
  ollama pull qwen2.5-coder:32b
  ollama pull nomic-embed-text
  ```

### Installation

```bash
# Clone the repository
cd redteam_agent

# Install Python dependencies
pip install -r requirements.txt

# Start the Docker infrastructure
docker-compose up -d

# Verify setup
redteam-agent status
```

### Basic Usage

```bash
# Start a new engagement
redteam-agent engage --target 192.168.1.100 --scope internal

# Run a quick scan
redteam-agent scan --target 192.168.1.100 --ports 1-1000

# Resume a paused engagement
redteam-agent resume --session-id abc123

# Generate a report
redteam-agent report --session-id abc123 --format markdown
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | What's new in v2.0 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture with Mermaid diagrams |
| [docs/ATTACK_SCENARIO.md](docs/ATTACK_SCENARIO.md) | Example attack on Metasploitable 3 |
| [docs/FUTURE_ENHANCEMENTS.md](docs/FUTURE_ENHANCEMENTS.md) | Roadmap and future improvements |

## 🛠️ CLI Commands

```bash
redteam-agent --help

Commands:
  engage     Start a new penetration testing engagement
  scan       Run reconnaissance scan on target
  resume     Resume a paused engagement
  report     Generate engagement report
  status     Show system status
  reset      Reset agent state (use with caution)
```

## 🔧 Configuration

Edit `config.yaml` to customize:

- LLM endpoints and parameters
- Docker sandbox settings
- Tool configurations
- Memory system parameters
- Logging levels

Example:
```yaml
llm:
  base_url: "http://localhost:11434/v1"
  model: "qwen2.5-coder:32b"
  embedding_model: "nomic-embed-text"

sandbox:
  image: "kalilinux/kali-rolling:latest"
  network_mode: "isolated"
  resource_limits:
    cpu: 2.0
    memory: "4g"
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_decision_engine.py -v
```

## 📁 Project Structure

```
redteam_agent/
├── code/
│   ├── __init__.py          # Package initialization
│   ├── models.py            # Pydantic data models
│   ├── decision_engine.py   # MCDA + Monte Carlo decision making
│   ├── world_model.py       # NetworkX graph persistence
│   ├── memory.py            # Two-level memory system
│   ├── tool_layer.py        # Tool abstraction & normalizers
│   ├── docker_sandbox.py    # Docker container management
│   ├── llm_client.py        # Ollama API wrapper
│   ├── orchestrator.py      # LangGraph StateGraph
│   └── cli.py               # Typer CLI interface
├── containers/
│   ├── Dockerfile           # Kali Linux sandbox image
│   └── docker-compose.yml   # Multi-container setup
├── docs/                    # Documentation
├── tests/                   # Unit tests
├── config.yaml              # Configuration
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## ⚠️ Disclaimer

This tool is designed for **authorized security testing only**. Always obtain proper written authorization before testing any systems you do not own. The authors are not responsible for misuse or any damages caused by improper use.

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## 🙏 Acknowledgments

- LangChain/LangGraph team for the orchestration framework
- Ollama for local LLM inference
- Kali Linux for the penetration testing distribution
- Qwen team for the excellent coder model

---

**Built with ❤️ by Senior Offensive Security Architect**
