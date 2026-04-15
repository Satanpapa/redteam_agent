"""Tool execution layer with semantic normalization and enrichment."""

from __future__ import annotations

import ipaddress
import json
import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import msgpack
import requests

from .models import ExecutionResult, MsfRpcConfig

logger = logging.getLogger(__name__)


class InputNormalizer:
    """Context-aware normalizers without regex dependency."""

    @staticmethod
    def normalize_target(raw: str) -> str:
        value = raw.strip()
        try:
            if "/" in value:
                network = ipaddress.ip_network(value, strict=False)
                return str(network)
            return str(ipaddress.ip_address(value))
        except ValueError:
            parsed = urlparse(value if "://" in value else f"http://{value}")
            if parsed.hostname:
                return parsed.hostname.lower()
            raise

    @staticmethod
    def normalize_command(command: str) -> list[str]:
        return shlex.split(command.strip())


@dataclass
class CVERecord:
    cve_id: str
    product: str
    version_prefix: str
    cvss: float
    exploitability: str


class DataEnricher:
    """Local enrichment pipeline with offline CVE inference."""

    def __init__(self, cve_db_path: str = "./data/local_cve.json") -> None:
        self.cve_db_path = Path(cve_db_path)
        self._db = self._load_db()

    def _load_db(self) -> list[CVERecord]:
        if not self.cve_db_path.exists():
            # Intentionally local placeholder dataset for fully offline mode.
            return [
                CVERecord("CVE-2017-0144", "smb", "1", 8.1, "high"),
                CVERecord("CVE-2021-41773", "apache", "2.4", 7.5, "medium"),
                CVERecord("CVE-2019-0708", "rdp", "6", 9.8, "critical"),
            ]
        data = json.loads(self.cve_db_path.read_text())
        return [CVERecord(**item) for item in data]

    def enrich_service(self, service: str, version: str) -> dict[str, Any]:
        matches = [
            rec
            for rec in self._db
            if rec.product.lower() in service.lower() and version.startswith(rec.version_prefix)
        ]
        return {
            "service": service,
            "version": version,
            "candidate_cves": [m.__dict__ for m in matches],
            "risk_hint": max((m.cvss for m in matches), default=0.0),
        }


class MetasploitRPC:
    def __init__(self, cfg: MsfRpcConfig) -> None:
        self.cfg = cfg
        proto = "https" if cfg.ssl else "http"
        self.url = f"{proto}://{cfg.host}:{cfg.port}{cfg.uri}"
        self.token: str | None = None

    def _call(self, method: str, *params: Any) -> Any:
        payload = msgpack.packb([method, *(params or ())], use_bin_type=True)
        response = requests.post(self.url, data=payload, timeout=30)
        response.raise_for_status()
        return msgpack.unpackb(response.content, raw=False)

    def login(self) -> bool:
        if not self.cfg.enabled:
            return False
        result = self._call("auth.login", self.cfg.user, self.cfg.password)
        self.token = result.get("token")
        return bool(self.token)

    def run_module(self, mtype: str, mname: str, options: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("Metasploit RPC token missing")
        return self._call("module.execute", self.token, mtype, mname, options)


class ToolLayer:
    def __init__(self, timeout: int = 180, metasploit_cfg: MsfRpcConfig | None = None) -> None:
        self.timeout = timeout
        self.normalizer = InputNormalizer()
        self.enricher = DataEnricher()
        self.msf = MetasploitRPC(metasploit_cfg or MsfRpcConfig())

    def run_local(self, action_id: str, command: str) -> ExecutionResult:
        args = self.normalizer.normalize_command(command)
        proc = subprocess.run(args, capture_output=True, text=True, timeout=self.timeout, check=False)
        return ExecutionResult(
            action_id=action_id,
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
        )

    def run_nmap_scan(self, target: str, flags: list[str] | None = None) -> ExecutionResult:
        normalized = self.normalizer.normalize_target(target)
        command = ["nmap", *(flags or ["-sV", "-Pn"]), normalized]
        return self.run_local(action_id="nmap_scan", command=shlex.join(command))

    def parse_nmap_summary(self, stdout: str) -> dict[str, Any]:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        ports: list[dict[str, Any]] = []
        for line in lines:
            tokens = line.split()
            if len(tokens) >= 3 and "/" in tokens[0] and tokens[1] == "open":
                svc = tokens[2]
                version = " ".join(tokens[3:]) if len(tokens) > 3 else "unknown"
                ports.append({"port": tokens[0], "service": svc, "version": version, "enrichment": self.enricher.enrich_service(svc, version)})
        return {"open_ports": ports, "raw_lines": len(lines)}
