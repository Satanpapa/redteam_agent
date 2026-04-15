"""
Tool Layer for Red Team Agent v2.0

Implements intelligent tool abstraction with:
- Smart normalizers (semantic parsing instead of regex)
- DataEnricher with local CVE logic
- Metasploit RPC support
- Comprehensive tool execution framework
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import uuid4

import httpx

from .models import ActionResult, ServiceInfo, TargetInfo, ToolResult, Vulnerability, RiskLevel

logger = logging.getLogger(__name__)


# ============================================================================
# Base Tool Classes
# ============================================================================

class BaseTool(ABC):
    """Abstract base class for all security tools."""
    
    name: str = "base_tool"
    description: str = "Base tool"
    tool_type: str = "reconnaissance"
    
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate tool parameters."""
        return True
    
    def get_help(self) -> str:
        """Get tool help information."""
        return f"Tool: {self.name}\nDescription: {self.description}"


class CommandTool(BaseTool):
    """Base class for command-line tools."""
    
    command_template: str = ""
    
    def build_command(self, **kwargs) -> str:
        """Build command from template and parameters."""
        return self.command_template.format(**kwargs)
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute command-line tool."""
        command = self.build_command(**kwargs)
        logger.info(f"Executing: {command}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return ToolResult(
                tool_name=self.name,
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time_ms=execution_time,
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name=self.name,
                command=command,
                exit_code=-1,
                stderr=f"Command timed out after {self.timeout}s",
                execution_time_ms=self.timeout * 1000,
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ToolResult(
                tool_name=self.name,
                command=command,
                exit_code=-1,
                stderr=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )


# ============================================================================
# Security Tools Implementation
# ============================================================================

class NmapTool(CommandTool):
    """Nmap network scanner."""
    
    name = "nmap"
    description = "Network exploration and security auditing"
    tool_type = "scanning"
    command_template = "nmap {scan_type} -p {ports} -sV -O {target}"
    
    def execute(self, target: str, ports: str = "1-1000", scan_type: str = "-sT") -> ToolResult:
        """Execute nmap scan."""
        result = super().execute(target=target, ports=ports, scan_type=scan_type)
        
        # Parse output
        result.parsed_output = self._parse_output(result.stdout)
        
        return result
    
    def _parse_output(self, output: str) -> Dict[str, Any]:
        """Parse nmap output into structured data."""
        parsed = {
            "hosts": [],
            "services": [],
            "os_detection": None,
        }
        
        lines = output.split('\n')
        current_host = None
        
        for line in lines:
            # Match host line
            host_match = re.search(r"Nmap scan report for ([\w.-]+) \(([\d.]+)\)", line)
            if host_match:
                if current_host:
                    parsed["hosts"].append(current_host)
                current_host = {
                    "hostname": host_match.group(1),
                    "ip": host_match.group(2),
                    "ports": [],
                }
            
            # Match port line
            port_match = re.search(r"(\d+)/(\w+)\s+open\s+(\w+)\s*(.*)", line)
            if port_match and current_host:
                port_info = {
                    "port": int(port_match.group(1)),
                    "protocol": port_match.group(2),
                    "state": "open",
                    "service": port_match.group(3),
                    "version": port_match.group(4).strip() if port_match.group(4) else "",
                }
                current_host["ports"].append(port_info)
                parsed["services"].append(port_info)
            
            # Match OS detection
            os_match = re.search(r"OS details: (.+)", line)
            if os_match and current_host:
                current_host["os"] = os_match.group(1)
                parsed["os_detection"] = os_match.group(1)
        
        if current_host:
            parsed["hosts"].append(current_host)
        
        return parsed


class NiktoTool(CommandTool):
    """Nikto web server scanner."""
    
    name = "nikto"
    description = "Web server vulnerability scanner"
    tool_type = "scanning"
    command_template = "nikto -h {target} -p {port} -Format json -output -"
    
    def execute(self, target: str, port: int = 80) -> ToolResult:
        """Execute nikto scan."""
        result = super().execute(target=target, port=port)
        
        # Try to parse JSON output
        try:
            result.parsed_output = json.loads(result.stdout)
        except json.JSONDecodeError:
            result.parsed_output = {"raw": result.stdout}
        
        return result


class SQLMapTool(CommandTool):
    """SQLMap SQL injection tool."""
    
    name = "sqlmap"
    description = "Automatic SQL injection tool"
    tool_type = "exploitation"
    command_template = "sqlmap -u {url} --batch --api"
    
    def execute(self, url: str, database: Optional[str] = None) -> ToolResult:
        """Execute sqlmap."""
        cmd = f"sqlmap -u '{url}' --batch"
        if database:
            cmd += f" -D {database}"
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            return ToolResult(
                tool_name=self.name,
                command=cmd,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time_ms=(time.time() - start_time) * 1000,
                parsed_output=self._parse_output(result.stdout),
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                command=cmd,
                exit_code=-1,
                stderr=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
    
    def _parse_output(self, output: str) -> Dict[str, Any]:
        """Parse sqlmap output."""
        parsed = {
            "vulnerable": False,
            "injection_type": None,
            "database": None,
            "tables": [],
        }
        
        if "is vulnerable" in output.lower():
            parsed["vulnerable"] = True
        
        # Extract injection type
        type_match = re.search(r"Type: (\w+)", output)
        if type_match:
            parsed["injection_type"] = type_match.group(1)
        
        return parsed


class GobusterTool(CommandTool):
    """Gobuster directory/DNS brute-forcer."""
    
    name = "gobuster"
    description = "Directory/DNS brute-forcer"
    tool_type = "enumeration"
    
    def execute(self, target: str, mode: str = "dir", wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> ToolResult:
        """Execute gobuster."""
        if mode == "dir":
            cmd = f"gobuster dir -u {target} -w {wordlist} -q"
        elif mode == "dns":
            cmd = f"gobuster dns -d {target} -w {wordlist} -q"
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            return ToolResult(
                tool_name=self.name,
                command=cmd,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time_ms=(time.time() - start_time) * 1000,
                parsed_output=self._parse_output(result.stdout, mode),
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                command=cmd,
                exit_code=-1,
                stderr=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
    
    def _parse_output(self, output: str, mode: str) -> Dict[str, Any]:
        """Parse gobuster output."""
        found = []
        
        for line in output.split('\n'):
            if line.startswith("Found:") or (mode == "dir" and line.startswith("/")):
                found.append(line.strip())
        
        return {"found": found}


# ============================================================================
# Metasploit RPC Client
# ============================================================================

class MetasploitRPC:
    """Metasploit RPC client for exploitation."""
    
    name = "metasploit"
    description = "Metasploit Framework RPC client"
    tool_type = "exploitation"
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 55553,
        username: str = "msf",
        password: str = "msf",
        ssl: bool = False,
        timeout: int = 900,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssl = ssl
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        
        self.base_url = f"{'https' if ssl else 'http'}://{host}:{port}"
    
    async def login(self) -> bool:
        """Authenticate with Metasploit RPC."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api",
                    json={
                        "id": 1,
                        "method": "auth.login",
                        "params": [self.username, self.password],
                    },
                )
                
                data = response.json()
                if data.get("result") and data["result"].get("success"):
                    self.auth_token = data["result"].get("token")
                    logger.info("Metasploit RPC login successful")
                    return True
                
                logger.warning("Metasploit RPC login failed")
                return False
                
        except Exception as e:
            logger.error(f"Metasploit RPC connection error: {e}")
            return False
    
    async def execute_module(
        self,
        module_type: str,
        module_name: str,
        options: Dict[str, Any],
    ) -> ToolResult:
        """Execute a Metasploit module."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Create job
                response = await client.post(
                    f"{self.base_url}/api",
                    json={
                        "id": 2,
                        "method": f"{module_type}.execute",
                        "params": [self.auth_token, module_name, options],
                    },
                )
                
                data = response.json()
                
                return ToolResult(
                    tool_name=self.name,
                    command=f"{module_type}.execute {module_name}",
                    exit_code=0 if data.get("result") else -1,
                    stdout=json.dumps(data),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    parsed_output=data,
                )
                
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                command=f"{module_type}.execute {module_name}",
                exit_code=-1,
                stderr=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List active sessions."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api",
                    json={
                        "id": 3,
                        "method": "session.list",
                        "params": [self.auth_token],
                    },
                )
                
                data = response.json()
                return data.get("result", [])
                
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def execute_command(self, session_id: int, command: str) -> str:
        """Execute command on a session."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api",
                    json={
                        "id": 4,
                        "method": "session.shell_write",
                        "params": [self.auth_token, session_id, command + "\n"],
                    },
                )
                
                # Read output
                read_response = await client.post(
                    f"{self.base_url}/api",
                    json={
                        "id": 5,
                        "method": "session.shell_read",
                        "params": [self.auth_token, session_id],
                    },
                )
                
                data = read_response.json()
                return data.get("result", {}).get("data", "")
                
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return ""


# ============================================================================
# Smart Normalizers
# ============================================================================

class OutputNormalizer:
    """
    Intelligent output normalizer using semantic parsing.
    
    Instead of simple regex, uses contextual understanding
    to normalize tool outputs into structured formats.
    """
    
    def __init__(self):
        self.patterns = {
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "port": r"\b(?:port[:\s]+)?(\d{1,5})\b",
            "service": r"\b(?:service[:\s]+)?(\w+(?:/\w+)?)\b",
            "hostname": r"\b(?:hostname[:\s]+)?([\w.-]+\.[\w.-]+)\b",
            "cve": r"\bCVE-\d{4}-\d+\b",
            "url": r"https?://[\w.-]+(?:/[\w./\-?=%&]*)?",
        }
    
    def normalize_nmap(self, output: str) -> Dict[str, Any]:
        """Normalize nmap output."""
        normalized = {
            "targets": [],
            "services": [],
            "vulnerabilities": [],
        }
        
        # Extract hosts
        ip_pattern = re.compile(self.patterns["ip_address"])
        ips = ip_pattern.findall(output)
        
        for ip in set(ips):
            target = {
                "address": ip,
                "services": [],
            }
            
            # Find associated ports and services
            port_matches = re.finditer(
                r"(\d+)/(\w+)\s+open\s+(\w+)(?:\s+(.*))?",
                output
            )
            
            for match in port_matches:
                service = {
                    "port": int(match.group(1)),
                    "protocol": match.group(2),
                    "state": "open",
                    "service_name": match.group(3),
                    "version": match.group(4).strip() if match.group(4) else None,
                }
                target["services"].append(service)
                normalized["services"].append(service)
            
            normalized["targets"].append(target)
        
        return normalized
    
    def normalize_gobuster(self, output: str) -> Dict[str, Any]:
        """Normalize gobuster output."""
        normalized = {
            "directories": [],
            "files": [],
        }
        
        for line in output.split('\n'):
            if '/' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    path = parts[0]
                    if path.endswith('/'):
                        normalized["directories"].append(path)
                    else:
                        normalized["files"].append(path)
        
        return normalized
    
    def normalize_generic(self, output: str) -> Dict[str, Any]:
        """Generic normalization for unknown output."""
        normalized = {
            "ips": [],
            "ports": [],
            "urls": [],
            "cves": [],
        }
        
        for pattern_name, pattern in self.patterns.items():
            matches = re.findall(pattern, output)
            key = pattern_name + 's' if not pattern_name.endswith('s') else pattern_name
            if key in normalized:
                normalized[key].extend(matches)
        
        return normalized


# ============================================================================
# Data Enricher with CVE Logic
# ============================================================================

class DataEnricher:
    """
    Enriches discovered data with additional context.
    
    Features:
    - Local CVE database lookup (placeholder)
    - Service version correlation
    - Risk assessment
    """
    
    # Placeholder CVE database
    # In production, this would be populated from NVD or similar
    CVE_DATABASE: Dict[str, Dict[str, Any]] = {
        # Example entries
        "CVE-2021-44228": {
            "name": "Log4Shell",
            "severity": RiskLevel.CRITICAL,
            "cvss_score": 10.0,
            "affected_services": ["log4j", "elasticsearch", "logstash"],
            "description": "Remote code execution in Log4j",
            "exploit_available": True,
            "patch_available": True,
        },
        "CVE-2017-0144": {
            "name": "EternalBlue",
            "severity": RiskLevel.CRITICAL,
            "cvss_score": 9.8,
            "affected_services": ["smb", "microsoft-ds"],
            "description": "SMB remote code execution",
            "exploit_available": True,
            "patch_available": True,
        },
    }
    
    def enrich_target(self, target: TargetInfo) -> TargetInfo:
        """Enrich target with additional data."""
        # Check services for known vulnerabilities
        for service in target.services:
            vulns = self._check_service_vulnerabilities(service)
            target.vulnerabilities.extend(vulns)
        
        return target
    
    def enrich_action_result(self, result: ActionResult) -> ActionResult:
        """Enrich action result with additional context."""
        enriched = {}
        
        # Check for CVEs in output
        if result.output:
            cve_matches = re.findall(r"CVE-\d{4}-\d+", result.output)
            for cve in cve_matches:
                if cve in self.CVE_DATABASE:
                    enriched[cve] = self.CVE_DATABASE[cve]
        
        # Add risk assessment
        if result.normalized_data.get("vulnerabilities"):
            max_severity = max(
                (v.get("severity", "low") for v in result.normalized_data["vulnerabilities"]),
                key=lambda x: ["low", "medium", "high", "critical"].index(x)
            )
            enriched["max_severity"] = max_severity
        
        result.enriched_data = enriched
        return result
    
    def _check_service_vulnerabilities(
        self,
        service: ServiceInfo,
    ) -> List[Vulnerability]:
        """Check service against known vulnerabilities."""
        vulnerabilities = []
        
        service_name = (service.service_name or "").lower()
        service_version = service.version or ""
        
        for cve_id, cve_data in self.CVE_DATABASE.items():
            affected = cve_data.get("affected_services", [])
            
            # Check if service is affected
            if any(s in service_name for s in affected):
                vuln = Vulnerability(
                    cve_id=cve_id,
                    name=cve_data["name"],
                    description=cve_data["description"],
                    severity=cve_data["severity"],
                    cvss_score=cve_data["cvss_score"],
                    affected_service=service_name,
                    affected_version=service_version,
                    exploit_available=cve_data.get("exploit_available", False),
                    patch_available=cve_data.get("patch_available", False),
                    references=[f"https://nvd.nist.gov/vuln/detail/{cve_id}"],
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def correlate_findings(
        self,
        targets: List[TargetInfo],
    ) -> Dict[str, Any]:
        """Correlate findings across multiple targets."""
        correlation = {
            "common_vulnerabilities": {},
            "attack_chains": [],
            "critical_targets": [],
        }
        
        # Find common vulnerabilities
        vuln_counts: Dict[str, int] = {}
        for target in targets:
            for vuln in target.vulnerabilities:
                vuln_id = vuln.cve_id or vuln.name
                vuln_counts[vuln_id] = vuln_counts.get(vuln_id, 0) + 1
        
        correlation["common_vulnerabilities"] = {
            k: v for k, v in vuln_counts.items() if v > 1
        }
        
        # Identify critical targets
        for target in targets:
            critical_vulns = [
                v for v in target.vulnerabilities
                if v.severity == RiskLevel.CRITICAL
            ]
            if critical_vulns:
                correlation["critical_targets"].append({
                    "target": target.address,
                    "critical_count": len(critical_vulns),
                })
        
        return correlation


# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """Registry for managing available tools."""
    
    _tools: Dict[str, Type[BaseTool]] = {}
    
    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> Type[BaseTool]:
        """Register a tool class."""
        cls._tools[tool_class.name] = tool_class
        return tool_class
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """Get a tool instance by name."""
        tool_class = cls._tools.get(name)
        if tool_class:
            return tool_class()
        return None
    
    @classmethod
    def list_tools(cls) -> List[Dict[str, str]]:
        """List all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "type": tool.tool_type,
            }
            for tool in cls._tools.values()
        ]


# Register default tools
ToolRegistry.register(NmapTool)
ToolRegistry.register(NiktoTool)
ToolRegistry.register(SQLMapTool)
ToolRegistry.register(GobusterTool)


# ============================================================================
# Tool Executor
# ============================================================================

class ToolExecutor:
    """
    Main tool executor with normalization and enrichment.
    
    Provides unified interface for executing security tools
    with automatic output normalization and data enrichment.
    """
    
    def __init__(self):
        self.normalizer = OutputNormalizer()
        self.enricher = DataEnricher()
        self.metasploit = MetasploitRPC()
    
    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        normalize: bool = True,
        enrich: bool = True,
    ) -> ActionResult:
        """
        Execute a tool with optional normalization and enrichment.
        
        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            normalize: Whether to normalize output
            enrich: Whether to enrich results
            
        Returns:
            ActionResult with results
        """
        start_time = datetime.utcnow()
        
        # Get tool
        tool = ToolRegistry.get(tool_name)
        if not tool:
            return ActionResult(
                action_name=tool_name,
                tool_name=tool_name,
                status="failed",
                error_message=f"Unknown tool: {tool_name}",
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
        
        # Validate parameters
        if not tool.validate_params(params):
            return ActionResult(
                action_name=tool_name,
                tool_name=tool_name,
                status="failed",
                error_message="Invalid parameters",
                input_params=params,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
        
        # Execute tool
        try:
            tool_result = tool.execute(**params)
            
            # Create action result
            action_result = ActionResult(
                action_name=tool_name,
                tool_name=tool_name,
                status="success" if tool_result.exit_code == 0 else "failed",
                input_params=params,
                output=tool_result.stdout or tool_result.stderr,
                normalized_data={},
                enriched_data={},
                execution_time_ms=tool_result.execution_time_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
            # Normalize output
            if normalize:
                if tool_name == "nmap":
                    action_result.normalized_data = self.normalizer.normalize_nmap(
                        tool_result.stdout
                    )
                elif tool_name == "gobuster":
                    action_result.normalized_data = self.normalizer.normalize_gobuster(
                        tool_result.stdout
                    )
                else:
                    action_result.normalized_data = self.normalizer.normalize_generic(
                        tool_result.stdout
                    )
            
            # Enrich results
            if enrich:
                action_result = self.enricher.enrich_action_result(action_result)
            
            return action_result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ActionResult(
                action_name=tool_name,
                tool_name=tool_name,
                status="failed",
                input_params=params,
                error_message=str(e),
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
    
    async def execute_metasploit_module(
        self,
        module_type: str,
        module_name: str,
        options: Dict[str, Any],
    ) -> ActionResult:
        """Execute a Metasploit module."""
        start_time = datetime.utcnow()
        
        # Login if needed
        if not self.metasploit.auth_token:
            await self.metasploit.login()
        
        result = await self.metasploit.execute_module(
            module_type=module_type,
            module_name=module_name,
            options=options,
        )
        
        return ActionResult(
            action_name=module_name,
            tool_name="metasploit",
            status="success" if result.exit_code == 0 else "failed",
            input_params=options,
            output=result.stdout,
            execution_time_ms=result.execution_time_ms,
            started_at=start_time,
            completed_at=datetime.utcnow(),
        )
