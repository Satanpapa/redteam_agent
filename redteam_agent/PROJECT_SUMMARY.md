# Project Summary — Improved Offline Autonomous Red Team Agent

## Что улучшено относительно предыдущей версии

1. **Замкнутый контур принятия решений**
   - Полностью реализован цикл `Planner → Decision Engine → Executor → Analyzer → Learner → Planner` на LangGraph с checkpointing (`MemorySaver`).
2. **Усиленный Decision Engine**
   - Добавлены MCDA, Monte Carlo симуляции, Pareto frontier, adaptive weight tuning на основе результата итерации.
3. **Полноценный World Model**
   - Используется `NetworkX MultiDiGraph` + устойчивое SQLite-хранилище узлов/ребер, включая upsert и query API.
4. **Двухуровневая память**
   - Tactical memory (SQLite) + semantic vector memory (ChromaDB) с единым `MemoryManager`.
5. **Интеллектуальный Tool Layer**
   - Нормализация результатов инструментов через структурный парсинг (без regex-центричной логики).
   - DataEnricher с локальной CVE-логикой и возможностью замены на офлайн NVD mirror.
   - Добавлен `Metasploit RPC` клиент (Open/offline friendly).
6. **Production-ready Docker sandbox**
   - Lifecycle management, resource limits, network isolation, volume controls, snapshots/restore, export/copy APIs.
7. **Новый LLM client для Ollama**
   - OpenAI-compatible wrapper с retries (tenacity), streaming и embeddings API.
8. **CLI уровня production**
   - Команды: `engage`, `scan`, `resume`, `report` на Typer + Rich.
9. **Документация и контейнеризация**
   - Обновлены README, архитектурная документация (Mermaid), attack scenario, roadmap, Dockerfile, compose.
10. **Тестирование**
   - Добавлен набор unit tests (>=5) для критических подсистем.

## Технический итог

Проект приведен к состоянию, близкому к production для полностью локальной red-team автоматизации, с четкой архитектурой, контролируемой песочницей, воспроизводимой памятью, и адаптивной стратегией принятия решений.
