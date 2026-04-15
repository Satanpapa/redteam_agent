# Attack Scenario: Metasploitable 3 (Offline Lab)

## Цель
Смоделировать контролируемую автономную атаку в локальном стенде против Metasploitable 3.

## Предусловия
- Kali runner в Docker
- Целевой узел Metasploitable 3 в отдельной lab-сети
- Разрешение на тестирование

## Этапы сценария
1. **Recon**
   - nmap service discovery (`-sV -oG -`)
2. **Service triage**
   - DataEnricher сопоставляет версии с локальным CVE knowledge base
3. **Web probing**
   - nikto по HTTP сервисам
4. **Selective exploitation planning**
   - Decision Engine выбирает действие по MCDA+Pareto
5. **(Опционально) Metasploit RPC execution**
   - запуск exploit module при достаточной уверенности
6. **Post-analysis**
   - обновление world graph, tactical notes, adaptive weights

## Условия остановки
- Достигнута цель (`foothold achieved`),
- риск превышает лимит,
- исчерпан `max_iterations`.
