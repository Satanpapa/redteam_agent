# Architecture

```mermaid
flowchart LR
    P[Planner Node\nLLM + Heuristics] --> D[Decision Engine\nMCDA + Monte Carlo + Pareto]
    D --> E[Executor Node\nTool Layer + Docker Sandbox]
    E --> A[Analyzer Node\nParsing + Enrichment + World Updates]
    A --> L[Learner Node\nReward + Weight Adaptation]
    L --> P

    E --> W[(World Model\nNetworkX + SQLite)]
    A --> W
    L --> M[(Memory System\nChroma + Tactical SQLite)]
    P --> M
```

## Основные узлы

- **Planner**: генерирует действия динамически через LLM и эвристики.
- **Decision Engine**: оценивает и выбирает действия с учетом trade-off.
- **Executor**: выполняет действия через sandbox + tool adapters.
- **Analyzer**: извлекает артефакты и обновляет world model.
- **Learner**: корректирует стратегию для следующих циклов.
