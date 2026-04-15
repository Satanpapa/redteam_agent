"""Tool abstraction layer with semantic normalizers and local enrichment."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    pass


class NmapNormalizer:
    """Parses Nmap XML into normalized structured records."""

    def normalize(self, xml_text: str) -> dict[str, Any]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ParseError("Invalid Nmap XML output") from exc

        hosts: list[dict[str, Any]] = []
        for host in root.findall("host"):
            addr = host.find("address")
            if addr is None:
                continue
            entry = {"ip": addr.attrib.get("addr"), "ports": [], "os": None}
            for port in host.findall("ports/port"):
                state = port.find("state")
                service = port.find("service")
                if state is not None and state.attrib.get("state") == "open":
                    entry["ports"].append(
                        {
                            "port": int(port.attrib.get("portid", 0)),
                            "protocol": port.attrib.get("protocol", "tcp"),
                            "service": service.attrib.get("name", "unknown") if service is not None else "unknown",
                        }
                    )
            hosts.append(entry)
        return {"hosts": hosts}


class NiktoNormalizer:
    """Tokenizes Nikto line output into findings, avoiding fragile one-shot regexes."""

    def normalize(self, output: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("+") or "OSVDB" in line:
                continue
            parts = [p.strip() for p in line[1:].split(":", maxsplit=1)]
            if len(parts) != 2:
                continue
            path, detail = parts
            findings.append({"path": path, "detail": detail})
        return {"findings": findings}


class DataEnricher:
    """Local enrichment via lightweight CVE/service heuristics.

    NOTE: Local CVE database is intentionally compact and can be replaced with offline NVD mirror.
    """

    _service_to_cve = {
        ("vsftpd", "2.3.4"): ["CVE-2011-2523"],
        ("samba", "3.0.20"): ["CVE-2007-2447"],
        ("proftpd", "1.3.3c"): ["CVE-2010-3867"],
    }

    def enrich_host(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        enriched["potential_cves"] = []
        for port in record.get("ports", []):
            service = port.get("service", "")
            version = port.get("version", "unknown")
            cves = self._service_to_cve.get((service, version), [])
            if cves:
                enriched["potential_cves"].extend(cves)
        return enriched


@dataclass
class MetasploitRPCConfig:
    host: str
    port: int
    user: str
    password: str
    ssl: bool = False


class MetasploitRPCClient:
    def __init__(self, config: MetasploitRPCConfig):
        self.config = config
        self.token: str | None = None
        proto = "https" if config.ssl else "http"
        self.url = f"{proto}://{config.host}:{config.port}/api/"
        self.client = httpx.Client(timeout=20)

    def login(self) -> str:
        response = self._call("auth.login", [self.config.user, self.config.password], include_token=False)
        self.token = response["token"]
        return self.token

    def _call(self, method: str, params: list[Any], include_token: bool = True) -> dict[str, Any]:
        payload = {"method": method, "params": []}
        if include_token:
            if not self.token:
                raise RuntimeError("Metasploit RPC token missing. Call login() first.")
            payload["params"].append(self.token)
        payload["params"].extend(params)
        resp = self.client.post(self.url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Metasploit RPC error: {data['error']}")
        return data

    def run_module(self, module_type: str, module_name: str, options: dict[str, Any]) -> dict[str, Any]:
        return self._call("module.execute", [module_type, module_name, options])


class ToolLayer:
    def __init__(self, metasploit_client: MetasploitRPCClient | None = None):
        self.nmap = NmapNormalizer()
        self.nikto = NiktoNormalizer()
        self.enricher = DataEnricher()
        self.metasploit = metasploit_client

    @staticmethod
    def normalize_target(target: str) -> str:
        try:
            return str(ipaddress.ip_network(target, strict=False))
        except ValueError:
            try:
                socket.gethostbyname(target)
                return target.lower()
            except socket.gaierror as exc:
                raise ParseError(f"Invalid target: {target}") from exc

    def normalize_tool_output(self, tool_name: str, output: str) -> dict[str, Any]:
        if tool_name == "nmap":
            return self.nmap.normalize(output)
        if tool_name == "nikto":
            return self.nikto.normalize(output)
        return {"raw": output}

    def enrich(self, normalized: dict[str, Any]) -> dict[str, Any]:
        hosts = normalized.get("hosts", [])
        return {"hosts": [self.enricher.enrich_host(h) for h in hosts]}

    def execute_metasploit(self, module_type: str, module_name: str, options: dict[str, Any]) -> dict[str, Any]:
        if not self.metasploit:
            raise RuntimeError("Metasploit client is not configured")
        if not self.metasploit.token:
            self.metasploit.login()
        return self.metasploit.run_module(module_type, module_name, options)
