# Project Summary: Red Team Agent vNext

## Что улучшено относительно предыдущей версии

1. **Архитектурная целостность**
   - Реализован замкнутый цикл `Planner → Decision → Executor → Analyzer → Learner → Planner` в LangGraph.
   - Добавлен checkpointer `MemorySaver` для восстановления сессий.

2. **Decision Intelligence**
   - Внедрены MCDA-оценка, Monte Carlo симуляция, Pareto ранжирование.
   - Добавлена epsilon-greedy exploration стратегия.
   - Реализована адаптивная корректировка весов после обучения.

3. **World Model и persistence**
   - Полноценный граф на NetworkX.
   - SQLite persistence для узлов/ребер.
   - Поддержка neighborhood-запросов и сериализации в отчет.

4. **Память агента (2 уровня)**
   - Tactical memory в SQLite для событий по фазам.
   - Semantic memory в ChromaDB для retrieval по контексту.

5. **Tool Layer продвинутого уровня**
   - Нормализация целевых данных (IP/CIDR/hostname) без regex.
   - Нормализация команд через безопасный shell tokenizer.
   - DataEnricher с локальной CVE-логикой (offline placeholder DB).
   - Добавлена интеграция с Metasploit RPC.

6. **Docker Sandbox Manager production-grade**
   - Lifecycle: start/exec/stop.
   - Resource limits (CPU/mem/pids).
   - Network isolation (internal bridge).
   - Volume control.
   - Snapshot и restore перед опасными действиями.

7. **LLM слой под Ollama**
   - OpenAI-compatible wrapper.
   - Retry c exponential backoff.
   - Streaming completion.

8. **CLI и UX**
   - Typer-команды: `engage`, `scan`, `resume`, `report`.
   - Конфигурируемый `config.yaml`.

9. **Документация и тестируемость**
   - Добавлены архитектурные документы и сценарий атаки.
   - Добавлен набор тестов (5+).

## Production-readiness

- Строгие type hints.
- Детализированное логирование.
- Явная обработка ошибок в критичных точках.
- Модульное разделение по доменам.
