# Attack Scenario: Metasploitable 3 (Authorized Lab)

## Цель

Автоматизированно построить attack path от внешнего recon к validated foothold в изолированной лаборатории.

## Этапы

1. **Recon**: `nmap -sV -Pn` по диапазону lab-сети.
2. **Service Profiling**: нормализация и enrichment сервисов с локальным CVE knowledge.
3. **Exploit Candidate Selection**: DecisionEngine выбирает шаг на Pareto frontier.
4. **Controlled Execution**: sandbox snapshot перед потенциально опасным действием.
5. **Post-analysis**: подтверждение эффекта, обновление world model.
6. **Learning Loop**: обновление весов stealth/impact/speed/confidence.

## Output артефакты

- JSON report по графу атаки.
- Tactical events timeline.
- Semantic memory entries для повторного reasoning.
