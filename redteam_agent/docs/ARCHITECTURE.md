# Red Team Agent v2.0 - Architecture

## System Overview

The Red Team Agent is an autonomous penetration testing system powered by local LLMs. It operates in a fully closed feedback loop, making intelligent decisions about attack strategies while maintaining safety and adaptability.

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        CLI[Typer CLI]
        API[REST API]
    end
    
    subgraph "Orchestration Layer"
        OG[LangGraph Orchestrator]
        CP[Checkpointing]
    end
    
    subgraph "Core Components"
        PL[Planner Node]
        DE[Decision Engine]
        EX[Executor]
        AN[Analyzer]
        LE[Learner]
    end
    
    subgraph "Knowledge Layer"
        WM[World Model<br/>NetworkX + SQLite]
        MEM[Memory System<br/>ChromaDB + SQLite]
    end
    
    subgraph "Tool Layer"
        TL[Tool Executor]
        NORM[Normalizers]
        ENR[DataEnricher]
    end
    
    subgraph "Infrastructure"
        DS[Docker Sandbox]
        LLM[Ollama LLM]
    end
    
    CLI --> OG
    API --> OG
    OG --> CP
    OG --> PL
    PL --> DE
    DE --> EX
    EX --> AN
    AN --> LE
    LE --> PL
    
    PL -.-> WM
    DE -.-> MEM
    EX -.-> TL
    TL --> NORM
    TL --> ENR
    EX --> DS
    PL --> LLM
    AN --> LLM
```

## Component Details

### 1. LangGraph Orchestrator

The orchestrator implements the agent's workflow as a state machine using LangGraph:

```mermaid
stateDiagram-v2
    [*] --> Planner
    Planner --> Decision
    Decision --> Executor
    Executor --> Analyzer
    Analyzer --> Learner
    Learner --> Planner: Continue
    Learner --> [*]: End
    
    note right of Planner
        Plans next action
        using LLM + heuristics
    end note
    
    note right of Decision
        MCDA + Monte Carlo
        Pareto optimization
    end note
    
    note right of Executor
        Executes tools
        in Docker sandbox
    end note
    
    note right of Analyzer
        Analyzes results
        with LLM
    end note
    
    note right of Learner
        Records outcomes
        Adapts weights
    end note
```

### 2. Decision Engine

Implements sophisticated decision-making:

```mermaid
flowchart LR
    A[Available Actions] --> B[MCDA Evaluation]
    B --> C[Monte Carlo Simulation]
    C --> D[Pareto Frontier]
    D --> E[Risk Assessment]
    E --> F{Risk OK?}
    F -->|Yes| G[Select Best Action]
    F -->|No| H[Block Action]
    G --> I[Execute]
    H --> J[Replan]
```

**Features:**
- Multi-Criteria Decision Analysis (MCDA)
- Monte Carlo simulation for outcome probability
- Pareto frontier optimization
- Adaptive weight adjustment
- Risk-aware filtering

### 3. World Model

Graph-based representation of the engagement state:

```mermaid
graph LR
    T1[Target 192.168.1.100] -->|hosts| S1[Service:445/SMB]
    T1 -->|hosts| S2[Service:80/HTTP]
    S1 -->|has_vulnerability| V1[CVE-2017-0144]
    S2 -->|has_vulnerability| V2[CVE-2021-44228]
    V1 -->|exploits| A1[Meterpreter]
    V2 -->|exploits| A2[Log4Shell]
    A1 -->|leads_to| C1[Credential Access]
    A2 -->|leads_to| C2[RCE]
```

**Node Types:**
- TARGET: IP addresses, hostnames
- SERVICE: Running services
- VULNERABILITY: CVEs, weaknesses
- CREDENTIAL: Discovered credentials
- ACTION: Executed actions
- FINDING: Analysis results

### 4. Memory System

Two-level memory architecture:

```mermaid
mindmap
  root((Memory System))
    Vector Store
      ChromaDB
      Semantic Search
      Long-term Memory
      Importance Weighted
    Tactical Memory
      SQLite
      Action Sequences
      Session Context
      Recent Actions
```

### 5. Tool Layer

Abstracted tool execution with intelligent parsing:

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant E as Executor
    participant N as Normalizer
    participant R as Enricher
    participant T as Tool
    
    O->>E: Execute(tool, params)
    E->>T: Run command
    T-->>E: Raw output
    E->>N: Normalize(output)
    N-->>E: Structured data
    E->>R: Enrich(data)
    R-->>E: Enhanced data
    E-->>O: ActionResult
```

### 6. Docker Sandbox

Isolated execution environment:

```mermaid
graph TB
    subgraph "Host System"
        HS[Host OS]
        DC[Docker Client]
    end
    
    subgraph "Docker Daemon"
        DD[Docker Daemon]
        NET[Isolated Network]
    end
    
    subgraph "Sandbox Container"
        KALI[Kali Linux]
        TOOLS[Security Tools]
        WS[Workspace]
    end
    
    DC --> DD
    DD --> NET
    NET --> KALI
    KALI --> TOOLS
    KALI --> WS
```

**Features:**
- Resource limits (CPU, memory)
- Network isolation
- Snapshot/restore
- Volume mounts
- Health monitoring

## Data Flow

```mermaid
flowchart TD
    Start[Engagement Start] --> Init[Initialize State]
    Init --> Plan[Generate Plan]
    Plan --> Eval[Evaluate Actions]
    Eval --> Select[Select Best Action]
    Select --> Exec[Execute in Sandbox]
    Exec --> Analyze[Analyze Results]
    Analyze --> Learn[Update Knowledge]
    Learn --> Check{Continue?}
    Check -->|Yes| Plan
    Check -->|No| Report[Generate Report]
    Report --> End[Engagement End]
    
    Learn -.-> WM[(World Model)]
    Learn -.-> MEM[(Memory)]
```

## Security Considerations

```mermaid
mindmap
  root((Safety Measures))
    Authorization
      Written consent required
      Scope enforcement
      Rules of engagement
    Risk Management
      Risk scoring
      High-risk blocking
      Confirmation prompts
    Isolation
      Docker containers
      Network separation
      Resource limits
    Monitoring
      Action logging
      Real-time status
      Kill switches
    Compliance
      Data retention policies
      Audit trails
      Report generation
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "External Services"
        OLLAMA[Ollama Server<br/>qwen2.5-coder:32b]
        CHROMA[ChromaDB]
    end
    
    subgraph "Red Team Agent"
        APP[Main Application]
        GRAPH[LangGraph]
        TOOLS[Tool Layer]
    end
    
    subgraph "Docker Infrastructure"
        SANDBOX[Sandbox Containers]
        MSF[Metasploit RPC]
        NET[Custom Network]
    end
    
    subgraph "Persistence"
        SQLITE[SQLite DBs]
        VOL[Volumes]
    end
    
    APP --> OLLAMA
    APP --> GRAPH
    GRAPH --> TOOLS
    TOOLS --> SANDBOX
    SANDBOX --> MSF
    APP --> SQLITE
    SANDBOX --> VOL
```

## Performance Characteristics

| Component | Latency | Throughput |
|-----------|---------|------------|
| LLM Inference | 2-10s | 10 tokens/s |
| Decision Engine | <100ms | 1000 evals/s |
| Tool Execution | 1-60s | Variable |
| Memory Search | <50ms | 100 queries/s |
| Graph Operations | <10ms | 10000 ops/s |

## Scalability

The architecture supports horizontal scaling through:
- Stateless orchestrator instances
- Distributed vector store
- Multiple sandbox containers
- Load-balanced LLM endpoints
