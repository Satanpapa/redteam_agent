# Attack Scenario: Metasploitable 3 (Offline Lab)

## Lab Topology
- RedTeam Agent: `192.168.56.10`
- Metasploitable 3 target: `192.168.56.101`
- Isolated host-only network

## Phase-by-phase flow
1. **Planner** proposes reconnaissance + vulnerability validation actions.
2. **Decision Engine** selects low-noise, high-value candidates from Pareto set.
3. **Executor** runs `nmap -sV` inside Kali sandbox and normalizes output.
4. **Analyzer** extracts lessons, confidence, and follow-up opportunities.
5. **Learner** updates weights, writes vector/tactical memory, closes loop.

## Example progression
- T1: Detect SMB + Samba 3.0.20
- T2: Enrich with `CVE-2007-2447`
- T3: Propose Metasploit module execution via RPC
- T4: Snapshot before exploit attempt
- T5: Restore and continue alternate path on failure
