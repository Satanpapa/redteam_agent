"""Tool execution layer with semantic normalizers, enrichment, and Metasploit RPC support."""

from __future__ import annotations

import ipaddress
import json
import logging
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import msgpack

from .models import ActionStatus, CVEResult, ServiceFingerprint, ToolExecutionRequest, ToolExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class MetasploitRPCConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    ssl: bool = False


class NmapOutputNormalizer:
    """Structured parser for grepable nmap output tokens (no regex-based extraction)."""

    def normalize(self, stdout: str) -> list[ServiceFingerprint]:
        findings: list[ServiceFingerprint] = []
        for line in stdout.splitlines():
            if "Ports:" not in line or "Host:" not in line:
                continue
            host = self._extract_host(line)
            if not host:
                continue
            ports_blob = line.split("Ports:", 1)[1]
            raw_ports = [part.strip() for part in ports_blob.split(",") if "/" in part]
            for entry in raw_ports:
                tokens = [t.strip() for t in entry.split("/")]
                if len(tokens) < 5:
                    continue
                try:
                    port = int(tokens[0])
                except ValueError:
                    continue
                if tokens[1] != "open":
                    continue
                service = tokens[4] if tokens[4] else "unknown"
                version = tokens[6] if len(tokens) > 6 and tokens[6] else None
                findings.append(ServiceFingerprint(host=host, port=port, service=service, version=version))
        return findings

    @staticmethod
    def _extract_host(line: str) -> str | None:
        head = line.split("Host:", 1)[1].strip() if "Host:" in line else ""
        candidate = head.split(" ", 1)[0]
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            return None


class NiktoOutputNormalizer:
    def normalize(self, stdout: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("-") or stripped.startswith("+"):
                continue
            if "OSVDB" in stripped or "CVE" in stripped or "Server:" in stripped:
                findings.append({"type": "web_finding", "detail": stripped})
        return findings


class DataEnricher:
    """Local-first CVE enricher based on CPE/service heuristics with offline DB placeholders."""

    def __init__(self) -> None:
        self._local_cve_db: dict[str, list[CVEResult]] = {
            "apache httpd:2.4.49": [
                CVEResult(
                    cve_id="CVE-2021-41773",
                    cvss=7.5,
                    summary="Path traversal and file disclosure in Apache HTTP Server 2.4.49.",
                    exploit_available=True,
                    references=["https://nvd.nist.gov/vuln/detail/CVE-2021-41773"],
                    affected_cpes=["cpe:2.3:a:apache:http_server:2.4.49:*:*:*:*:*:*:*"],
                )
            ],
            # Placeholder DB can be replaced by offline NVD mirror.
        }

    def enrich_services(self, fingerprints: list[ServiceFingerprint]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in fingerprints:
            key = f"{item.product or item.service}:{item.version}".lower() if item.version else item.service.lower()
            cves = self._local_cve_db.get(key, [])
            enriched.append(
                {
                    "service": item.model_dump(),
                    "cves": [cve.model_dump() for cve in cves],
                    "risk_score": max([c.cvss or 0 for c in cves], default=0.0),
                }
            )
        return enriched


class MetasploitRPCClient:
    def __init__(self, config: MetasploitRPCConfig) -> None:
        self.config = config
        self._token: str | None = None
        proto = "https" if config.ssl else "http"
        self.url = f"{proto}://{config.host}:{config.port}/api/"

    def login(self) -> str:
        if not self.config.enabled:
            raise RuntimeError("Metasploit RPC is disabled")
        payload = ["auth.login", self.config.username, self.config.password]
        data = self._post(payload)
        token = data.get("token")
        if not token:
            raise RuntimeError(f"MSF RPC authentication failed: {data}")
        self._token = token
        return token

    def call(self, method: str, *args: Any) -> dict[str, Any]:
        if not self._token:
            self.login()
        payload = [method, self._token, *args]
        return self._post(payload)

    def _post(self, payload: list[Any]) -> dict[str, Any]:
        packed = msgpack.packb(payload)
        with httpx.Client(timeout=30.0, verify=self.config.ssl) as client:
            response = client.post(self.url, content=packed, headers={"Content-Type": "binary/message-pack"})
            response.raise_for_status()
        unpacked = msgpack.unpackb(response.content, strict_map_key=False)
        return {self._decode(k): self._decode(v) for k, v in unpacked.items()}

    def _decode(self, value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {self._decode(k): self._decode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._decode(v) for v in value]
        return value


class ToolLayer:
    def __init__(self, workdir: str, metasploit_config: MetasploitRPCConfig | None = None) -> None:
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.nmap_normalizer = NmapOutputNormalizer()
        self.nikto_normalizer = NiktoOutputNormalizer()
        self.enricher = DataEnricher()
        self.msf = MetasploitRPCClient(metasploit_config) if metasploit_config else None

    def execute(self, req: ToolExecutionRequest) -> ToolExecutionResult:
        started = time.time()
        cmd = [req.command, *req.args]
        logger.info("Executing tool: %s", shlex.join(cmd))

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=req.timeout_seconds,
                check=False,
            )
            status = ActionStatus.SUCCESS if proc.returncode == 0 else ActionStatus.FAILED
            result = ToolExecutionResult(
                tool_name=req.tool_name,
                command=shlex.join(cmd),
                status=status,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_seconds=time.time() - started,
            )
        except subprocess.TimeoutExpired as exc:
            result = ToolExecutionResult(
                tool_name=req.tool_name,
                command=shlex.join(cmd),
                status=ActionStatus.FAILED,
                stdout=exc.stdout or "",
                stderr=f"Timeout after {req.timeout_seconds}s",
                exit_code=-1,
                duration_seconds=time.time() - started,
            )

        result.normalized_findings = self._normalize_findings(req.tool_name, result.stdout)
        return result

    def _normalize_findings(self, tool_name: str, stdout: str) -> list[dict[str, Any]]:
        if tool_name == "nmap":
            services = self.nmap_normalizer.normalize(stdout)
            return self.enricher.enrich_services(services)
        if tool_name == "nikto":
            return self.nikto_normalizer.normalize(stdout)
        return []

    def metasploit_run_module(self, module_type: str, module_name: str, options: dict[str, Any]) -> dict[str, Any]:
        if not self.msf:
            raise RuntimeError("Metasploit RPC not configured")
        self.msf.call("module.execute", module_type, module_name, options)
        return {
            "module_type": module_type,
            "module_name": module_name,
            "options": options,
            "status": "submitted",
        }

    def save_raw_output(self, filename: str, payload: dict[str, Any]) -> Path:
        path = self.workdir / filename
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
