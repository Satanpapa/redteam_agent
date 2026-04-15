# Architecture

```mermaid
flowchart LR
    U[CLI / Operator] --> O[Orchestrator\nLangGraph StateGraph]
    O --> P[Planner Node\nLLM + Heuristics]
    P --> D[Decision Engine\nMCDA + Monte Carlo + Pareto]
    D --> E[Executor Node]
    E --> S[Docker Sandbox Manager\nKali Container]
    E --> T[Tool Layer\nNormalizers + Metasploit RPC]
    T --> A[Analyzer Node]
    A --> L[Learner Node]
    L --> P

    O --> M[Memory System]
    M --> V[Vector Memory\nChromaDB]
    M --> X[Tactical Memory\nSQLite]

    O --> W[World Model]
    W --> G[NetworkX Graph]
    W --> DB[(SQLite persistence)]

    O --> C[Checkpointing\nMemorySaver]
```

## Dataflow
1. Planner генерирует действия (LLM + эвристики).
2. Decision Engine ранжирует действия и выбирает Pareto-efficient кандидат.
3. Executor запускает инструмент в Docker sandbox.
4. Analyzer извлекает сущности, строит вывод и сигнал успеха.
5. Learner обновляет веса стратегии, память и world model.
6. Цикл повторяется до `max_iterations` или `halt`.
